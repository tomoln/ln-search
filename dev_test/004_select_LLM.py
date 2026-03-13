from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI

STEP_NAME = "004_select_LLM"


def load_context() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parent.parent
    base_dir = project_root / "dev_test"
    paths = {
        "project_root": project_root,
        "base_dir": base_dir,
        "config_dir": base_dir / "config",
        "io_dir": base_dir / "io",
        "input_dir": base_dir / "io" / "input",
        "output_dir": base_dir / "io" / "output",
        "tmp_dir": base_dir / "io" / "tmp",
        "logs_dir": base_dir / "logs",
        "settings": base_dir / "config" / "settings.json",
        "llm_list": base_dir / "config" / "llm_list.json",
        "init_state": base_dir / "io" / "tmp" / "001_initialize_state.json",
        "step_output": base_dir / "io" / "output" / "004_select_LLM.txt",
        "selected_json": base_dir / "io" / "tmp" / "004_selected_llm.json",
    }
    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "paths": paths,
        "settings": {},
        "selected_search_api": None,
        "selected_llm": None,
        "thresholds": {},
    }


def load_settings() -> dict[str, Any]:
    context = load_context()
    settings_path = context["paths"]["settings"]
    if settings_path.exists():
        return json.loads(settings_path.read_text(encoding="utf-8"))
    return {}


def get_logger(step_name: str) -> logging.Logger:
    context = load_context()
    logs_dir = context["paths"]["logs_dir"]
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(step_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    file_handler = logging.FileHandler(logs_dir / f"{step_name}.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)
    return logger


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def read_text_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, records: list[dict[str, Any]], mode: str = "w") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str, mode: str = "w") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8", newline="\n") as f:
        f.write(text)


def validate_inputs(required_paths: list[Path]) -> None:
    missing = [str(p) for p in required_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files: {missing}")


def validate_dependencies() -> None:
    return None


def handle_step_error(step_name: str, error: Exception) -> None:
    logger = get_logger(step_name)
    logger.exception("Step failed: %s", error)
    raise


def _load_llm_candidates(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("llms", [])


def _is_budget_available(provider_name: str) -> bool:
    env_name = f"FREE_TIER_REMAINING_{provider_name.upper()}"
    raw = os.getenv(env_name)
    if raw is None:
        return True
    return raw.strip().lower() in {"1", "true", "yes", "y", "ok"}


def _healthcheck_ok(provider_name: str, key_env: str, model: str) -> bool:
    provider = provider_name.strip().lower()
    if provider == "openai":
        api_key = os.getenv(key_env, "")
        if not api_key:
            return False
        try:
            client = OpenAI(api_key=api_key)
            _ = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0,
            )
            return True
        except Exception:
            return False

    healthcheck_url = None
    if not healthcheck_url:
        return False
    try:
        response = requests.get(healthcheck_url, timeout=5)
        return 200 <= response.status_code < 500
    except requests.RequestException:
        return False


def run_step(context: dict[str, Any]) -> dict[str, Any]:
    logger = get_logger(STEP_NAME)
    try:
        paths = context["paths"]
        validate_inputs([paths["llm_list"], paths["init_state"]])
        candidates = sorted(
            _load_llm_candidates(paths["llm_list"]),
            key=lambda x: int(x.get("priority", 9999)),
        )

        selected: dict[str, Any] | None = None
        for llm in candidates:
            name = str(llm.get("name", "")).strip()
            if not name:
                continue
            key_env = llm.get("key_env") or f"LLM_API_{name.upper()}_KEY"
            model = llm.get("model", "gpt-4o-mini")
            if not os.getenv(key_env):
                logger.info("Skip %s: missing key env %s", name, key_env)
                continue
            if not _is_budget_available(name):
                logger.info("Skip %s: budget unavailable", name)
                continue
            if not _healthcheck_ok(name, key_env, model):
                logger.info("Skip %s: healthcheck failed", name)
                continue

            selected = {
                "name": name,
                "key_env": key_env,
                "model": model,
                "latency_hint_ms": llm.get("latency_hint_ms", None),
                "cost_hint_per_1k": llm.get("cost_hint_per_1k", None),
                "selected_reason": "available and healthy",
                "selected_at": datetime.now(timezone.utc).isoformat(),
            }
            break

        if selected is None:
            raise RuntimeError("No available LLM was found.")

        write_text(paths["step_output"], json.dumps(selected, ensure_ascii=False, indent=2))
        write_text(paths["selected_json"], json.dumps(selected, ensure_ascii=False, indent=2))
        context["selected_llm"] = selected
        logger.info("Selected LLM: %s", selected["name"])
        return context
    except Exception as error:  # pragma: no cover
        handle_step_error(STEP_NAME, error)
        return context


if __name__ == "__main__":
    run_step(load_context())
