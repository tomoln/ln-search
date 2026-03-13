from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

STEP_NAME = "005_score_LLM"


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
        "url_records": base_dir / "io" / "output" / "003_get_url.txt",
        "selected_llm": base_dir / "io" / "tmp" / "004_selected_llm.json",
        "step_output": base_dir / "io" / "output" / "005_score_LLM.txt",
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
    return {
        "score_threshold": 0.6,
        "trusted_domains": ["wikipedia.org", "github.com", "qiita.com", "docs.python.org"],
        "score_weight": {"relevance": 0.6, "freshness": 0.2, "reliability": 0.2},
    }


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


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if t}


def _relevance_score(query: str, title: str, snippet: str) -> float:
    q_tokens = _tokenize(query)
    t_tokens = _tokenize(f"{title} {snippet}")
    if not q_tokens:
        return 0.0
    return len(q_tokens & t_tokens) / len(q_tokens)


def _freshness_score(title: str, snippet: str) -> float:
    text = f"{title} {snippet}"
    year_matches = re.findall(r"(20\d{2})", text)
    if not year_matches:
        return 0.5
    latest = max(int(y) for y in year_matches)
    current_year = datetime.now(timezone.utc).year
    diff = max(current_year - latest, 0)
    return max(0.0, min(1.0, 1.0 - diff * 0.2))


def _reliability_score(url: str, trusted_domains: list[str]) -> float:
    domain = urlparse(url).netloc.lower()
    if any(domain.endswith(td) for td in trusted_domains):
        return 1.0
    if domain:
        return 0.5
    return 0.0


def run_step(context: dict[str, Any]) -> dict[str, Any]:
    logger = get_logger(STEP_NAME)
    try:
        settings = load_settings()
        paths = context["paths"]
        validate_inputs([paths["url_records"], paths["selected_llm"]])

        records = read_jsonl(paths["url_records"])
        selected_llm = json.loads(paths["selected_llm"].read_text(encoding="utf-8"))
        threshold = float(settings.get("score_threshold", 0.6))
        weights = settings.get("score_weight", {"relevance": 0.6, "freshness": 0.2, "reliability": 0.2})
        trusted_domains = settings.get("trusted_domains", [])

        scored_records: list[dict[str, Any]] = []
        for row in records:
            query = row.get("query", "")
            title = row.get("title", "")
            snippet = row.get("snippet", "")
            url = row.get("url", "")

            relevance = _relevance_score(query, title, snippet)
            freshness = _freshness_score(title, snippet)
            reliability = _reliability_score(url, trusted_domains)
            score = (
                relevance * float(weights.get("relevance", 0.6))
                + freshness * float(weights.get("freshness", 0.2))
                + reliability * float(weights.get("reliability", 0.2))
            )
            accepted = score >= threshold

            scored_records.append(
                {
                    "query": query,
                    "url": url,
                    "score": round(score, 4),
                    "accepted": accepted,
                    "relevance": round(relevance, 4),
                    "freshness": round(freshness, 4),
                    "reliability": round(reliability, 4),
                    "llm": selected_llm.get("name", ""),
                    "scored_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        write_jsonl(paths["step_output"], scored_records, mode="w")
        logger.info("Scored %s URL records.", len(scored_records))
        return context
    except Exception as error:  # pragma: no cover
        handle_step_error(STEP_NAME, error)
        return context


if __name__ == "__main__":
    run_step(load_context())
