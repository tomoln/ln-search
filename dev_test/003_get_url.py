from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

STEP_NAME = "003_get_url"


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
        "input_queries": base_dir / "io" / "input" / "003_get_url_input.txt",
        "selected_api": base_dir / "io" / "tmp" / "002_selected_search_api.json",
        "step_output": base_dir / "io" / "output" / "003_get_url.txt",
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
    return {"max_results_per_query": 10}


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


def _search_with_serper(
    api_key: str,
    query: str,
    max_results: int,
    timeout_sec: int,
    max_retries: int,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    endpoint = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": max_results}
    connect_timeout = min(5, max(1, timeout_sec))
    read_timeout = max(1, timeout_sec)

    response: requests.Response | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=(connect_timeout, read_timeout),
            )
            if response.status_code == 429 and attempt < max_retries:
                wait_sec = min(2 ** (attempt - 1), 4)
                logger.warning("Serper rate-limited (429). Retrying in %ss.", wait_sec)
                time.sleep(wait_sec)
                continue
            response.raise_for_status()
            break
        except requests.Timeout as error:
            if attempt >= max_retries:
                raise TimeoutError(f"Serper request timed out after {max_retries} attempts") from error
            wait_sec = min(2 ** (attempt - 1), 4)
            logger.warning("Serper timeout. Retrying in %ss (attempt %s/%s).", wait_sec, attempt + 1, max_retries)
            time.sleep(wait_sec)
        except requests.RequestException as error:
            status_code = getattr(getattr(error, "response", None), "status_code", None)
            if status_code in {500, 502, 503, 504} and attempt < max_retries:
                wait_sec = min(2 ** (attempt - 1), 4)
                logger.warning("Serper HTTP %s. Retrying in %ss.", status_code, wait_sec)
                time.sleep(wait_sec)
                continue
            raise

    if response is None:
        return []

    data = response.json()
    organic = data.get("organic", [])
    records: list[dict[str, Any]] = []
    for index, item in enumerate(organic, start=1):
        records.append(
            {
                "rank": index,
                "url": item.get("link", ""),
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
            }
        )
    return records


def _perform_search(
    provider_name: str,
    key_env: str,
    query: str,
    max_results: int,
    timeout_sec: int,
    max_retries: int,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    api_key = os.getenv(key_env, "")
    if not api_key:
        logger.warning("API key env var '%s' is empty. Returning no results.", key_env)
        return []

    provider = provider_name.strip().lower()
    if provider == "serper":
        return _search_with_serper(api_key, query, max_results, timeout_sec, max_retries, logger)
    return []


def run_step(context: dict[str, Any]) -> dict[str, Any]:
    logger = get_logger(STEP_NAME)
    try:
        settings = load_settings()
        paths = context["paths"]
        validate_inputs([paths["input_queries"], paths["selected_api"]])

        selected = json.loads(paths["selected_api"].read_text(encoding="utf-8"))
        provider_name = selected["name"]
        key_env = selected["key_env"]
        queries = read_text_lines(paths["input_queries"])
        max_results = int(settings.get("max_results_per_query", 10))
        timeout_sec = int(settings.get("request_timeout_sec", 20))
        max_retries = int(settings.get("request_max_retries", 2))

        all_records: list[dict[str, Any]] = []
        total_queries = len(queries)
        for index, query in enumerate(queries, start=1):
            logger.info("Searching query %s/%s: %s", index, total_queries, query)
            try:
                hits = _perform_search(
                    provider_name,
                    key_env,
                    query,
                    max_results,
                    timeout_sec,
                    max_retries,
                    logger,
                )
            except Exception as error:  # pragma: no cover
                logger.warning("Search failed for query '%s': %s", query, error)
                hits = []
            if not hits:
                all_records.append(
                    {
                        "query": query,
                        "rank": None,
                        "url": "",
                        "title": "",
                        "snippet": "",
                        "provider": provider_name,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "status": "no_results",
                    }
                )
                continue

            for hit in hits:
                all_records.append(
                    {
                        "query": query,
                        "rank": hit.get("rank"),
                        "url": hit.get("url", ""),
                        "title": hit.get("title", ""),
                        "snippet": hit.get("snippet", ""),
                        "provider": provider_name,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "status": "ok",
                    }
                )

        write_jsonl(paths["step_output"], all_records, mode="a")
        logger.info("Collected %s URL records.", len(all_records))
        return context
    except Exception as error:  # pragma: no cover
        handle_step_error(STEP_NAME, error)
        return context


if __name__ == "__main__":
    run_step(load_context())
