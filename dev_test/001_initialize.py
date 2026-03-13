from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEP_NAME = "001_initialize"


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
        "llm_list": base_dir / "config" / "llm_list.json",
        "state_file": base_dir / "io" / "tmp" / "001_initialize_state.json",
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
        "clear_tmp_on_start": True,
        "score_threshold": 0.6,
        "required_libraries": ["requests", "bs4", "trafilatura"],
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

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
    logger.addHandler(stream_handler)

    return logger


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
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
    settings = load_settings()
    required = settings.get("required_libraries", ["requests", "bs4", "trafilatura"])
    missing: list[str] = []
    for lib in required:
        # Use module discovery only to avoid side effects or slow imports during initialization.
        if importlib.util.find_spec(lib) is None:
            missing.append(lib)
    if missing:
        raise ImportError(f"Missing dependencies: {missing}")


def handle_step_error(step_name: str, error: Exception) -> None:
    logger = get_logger(step_name)
    logger.exception("Step failed: %s", error)
    raise


def _clear_directory(directory: Path) -> None:
    if not directory.exists():
        return
    for child in directory.iterdir():
        if child.is_file():
            child.unlink(missing_ok=True)
        elif child.is_dir():
            shutil.rmtree(child, ignore_errors=True)


def run_step(context: dict[str, Any]) -> dict[str, Any]:
    logger = get_logger(STEP_NAME)
    try:
        settings = load_settings()
        paths = context["paths"]

        for key in ("config_dir", "io_dir", "input_dir", "output_dir", "tmp_dir", "logs_dir"):
            paths[key].mkdir(parents=True, exist_ok=True)

        if settings.get("clear_tmp_on_start", True):
            _clear_directory(paths["tmp_dir"])

        if settings.get("clear_output_on_start", False):
            _clear_directory(paths["output_dir"])

        if sys.version_info < (3, 13):
            raise RuntimeError("Python 3.13 or newer is required.")

        validate_dependencies()

        state = {
            "step": STEP_NAME,
            "run_id": context["run_id"],
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "python_version": sys.version,
            "status": "ok",
        }
        write_text(paths["state_file"], json.dumps(state, ensure_ascii=False, indent=2))

        context["settings"] = settings
        context["thresholds"] = {"score_threshold": settings.get("score_threshold", 0.6)}
        logger.info("Initialization complete.")
        return context
    except Exception as error:  # pragma: no cover
        handle_step_error(STEP_NAME, error)
        return context


if __name__ == "__main__":
    run_step(load_context())
