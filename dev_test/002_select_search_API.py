from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

STEP_NAME = "002_select_search_API"


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
        "search_api_list": base_dir / "config" / "search_api_list.json",
        "init_state": base_dir / "io" / "tmp" / "001_initialize_state.json",
        "step_output": base_dir / "io" / "output" / "002_select_search_API.txt",
        "selected_json": base_dir / "io" / "tmp" / "002_selected_search_api.json",
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


def _load_search_api_candidates(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("apis", [])


def _is_free_tier_available(provider_name: str) -> bool:
    env_name = f"FREE_TIER_REMAINING_{provider_name.upper()}"
    raw = os.getenv(env_name)
    if raw is None:
        return True
    return raw.strip().lower() in {"1", "true", "yes", "y", "ok"}


def _is_healthcheck_ok(provider_name: str, key_env: str) -> bool:
    settings = load_settings()
    allow_insecure_tls_fallback = bool(settings.get("allow_insecure_tls_fallback", True))
    if allow_insecure_tls_fallback:
        urllib3.disable_warnings(InsecureRequestWarning)
    api_key = os.getenv(key_env, "")
    if not api_key:
        return False

    def _request_with_tls_fallback(method: str, url: str, **kwargs: Any) -> requests.Response:
        try:
            return requests.request(method=method, url=url, **kwargs)
        except requests.exceptions.SSLError as error:
            if not allow_insecure_tls_fallback:
                raise
            host = urlparse(url).hostname or "unknown-host"
            if host not in {"google.serper.dev", "api.search.brave.com"}:
                raise
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["verify"] = False
            return requests.request(method=method, url=url, **fallback_kwargs)

    provider = provider_name.strip().lower()
    try:
        if provider == "brave":
            response = _request_with_tls_fallback(
                method="GET",
                url="https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                params={"q": "healthcheck", "count": 1},
                timeout=8,
            )
            return response.status_code == 200

        if provider == "serper":
            response = _request_with_tls_fallback(
                method="POST",
                url="https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": "healthcheck", "num": 1},
                timeout=8,
            )
            return response.status_code == 200
    except requests.RequestException:
        return False

    return False


def _mask_key(key_value: str) -> str:
    if len(key_value) <= 6:
        return "*" * len(key_value)
    return f"{key_value[:3]}***{key_value[-3:]}"


def run_step(context: dict[str, Any]) -> dict[str, Any]:
    logger = get_logger(STEP_NAME)
    try:
        settings = load_settings()
        paths = context["paths"]
        validate_inputs([paths["search_api_list"], paths["init_state"]])
        allow_healthcheck_fallback = bool(settings.get("allow_search_api_healthcheck_fallback", True))
        candidates = sorted(
            _load_search_api_candidates(paths["search_api_list"]),
            key=lambda x: int(x.get("priority", 9999)),
        )

        selected: dict[str, Any] | None = None
        for api in candidates:
            name = str(api.get("name", "")).strip()
            if not name:
                continue
            key_env = api.get("key_env") or f"SEARCH_API_{name.upper()}_KEY"
            key_value = os.getenv(key_env, "")
            if not key_value:
                logger.info("Skip %s: missing key env %s", name, key_env)
                continue

            free_tier_ok = _is_free_tier_available(name)
            health_ok = _is_healthcheck_ok(name, key_env)
            if not health_ok:
                if not allow_healthcheck_fallback:
                    logger.info("Skip %s: healthcheck failed", name)
                    continue
                logger.warning(
                    "Healthcheck failed for %s, but selecting as fallback because allow_search_api_healthcheck_fallback=true",
                    name,
                )
                selected = {
                    "name": name,
                    "key_env": key_env,
                    "api_key_masked": _mask_key(key_value),
                    "selected_reason": "fallback (healthcheck failed)",
                    "selected_at": datetime.now(timezone.utc).isoformat(),
                }
                break

            reason = "free tier available" if free_tier_ok else "fallback (free tier unknown/exhausted)"
            selected = {
                "name": name,
                "key_env": key_env,
                "api_key_masked": _mask_key(key_value),
                "selected_reason": reason,
                "selected_at": datetime.now(timezone.utc).isoformat(),
            }
            break

        if selected is None:
            raise RuntimeError("No available search API was found.")

        write_text(paths["step_output"], json.dumps(selected, ensure_ascii=False, indent=2))
        write_text(paths["selected_json"], json.dumps(selected, ensure_ascii=False, indent=2))
        context["selected_search_api"] = selected
        logger.info("Selected search API: %s", selected["name"])
        return context
    except Exception as error:  # pragma: no cover
        handle_step_error(STEP_NAME, error)
        return context


if __name__ == "__main__":
    run_step(load_context())
