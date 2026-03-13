from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

STEP_NAME = "006_scraping"


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
        "scored_records": base_dir / "io" / "output" / "005_score_LLM.txt",
        "step_output": base_dir / "io" / "output" / "006_scraping.txt",
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
    return {"request_timeout_sec": 20, "enable_js_render": False}


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


def _fetch_html(
    url: str,
    timeout: int,
    allow_insecure_tls_fallback: bool,
) -> requests.Response:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ln-search/1.0)"}
    try:
        return requests.get(url, timeout=timeout, headers=headers)
    except requests.exceptions.SSLError:
        if not allow_insecure_tls_fallback:
            raise
        # Retry once without certificate verification only when TLS validation fails.
        return requests.get(url, timeout=timeout, headers=headers, verify=False)


def run_step(context: dict[str, Any]) -> dict[str, Any]:
    logger = get_logger(STEP_NAME)
    try:
        settings = load_settings()
        allow_insecure_tls_fallback = bool(settings.get("allow_insecure_tls_fallback", True))
        if allow_insecure_tls_fallback:
            urllib3.disable_warnings(InsecureRequestWarning)
        paths = context["paths"]
        validate_inputs([paths["scored_records"]])
        scored = read_jsonl(paths["scored_records"])

        timeout = int(settings.get("request_timeout_sec", 20))
        enable_js_render = bool(settings.get("enable_js_render", False))
        if enable_js_render:
            logger.info("JS rendering option is enabled in config, but this implementation uses requests only.")

        scrape_records: list[dict[str, Any]] = []
        for row in scored:
            if not row.get("accepted", False):
                continue
            url = row.get("url", "")
            if not url:
                continue
            try:
                response = _fetch_html(url=url, timeout=timeout, allow_insecure_tls_fallback=allow_insecure_tls_fallback)
                safe_html = response.text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
                scrape_records.append(
                    {
                        "url": url,
                        "status_code": response.status_code,
                        "raw_html": safe_html,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "status": "ok",
                    }
                )
            except requests.RequestException as error:
                scrape_records.append(
                    {
                        "url": url,
                        "status_code": None,
                        "raw_html": "",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "status": "error",
                        "error": str(error),
                    }
                )

        write_jsonl(paths["step_output"], scrape_records, mode="w")
        logger.info("Scraped %s URLs.", len(scrape_records))
        return context
    except Exception as error:  # pragma: no cover
        handle_step_error(STEP_NAME, error)
        return context


if __name__ == "__main__":
    run_step(load_context())
