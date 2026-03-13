from __future__ import annotations

import importlib.util
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from env_bootstrap import bootstrap_runtime_env

STEP_FILES = [
    "001_initialize.py",
    "002_select_search_API.py",
    "003_get_url.py",
    "004_select_LLM.py",
    "005_score_LLM.py",
    "006_scraping.py",
    "007_extraction.py",
    "008_out.py",
]


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
        "summary": base_dir / "io" / "output" / "pipeline_run_summary.json",
    }
    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "paths": paths,
        "settings": {},
        "selected_search_api": None,
        "selected_llm": None,
        "thresholds": {},
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


def _load_module(module_path: Path) -> Any:
    module_name = module_path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_step_by_name(step_file: str, context: dict[str, Any]) -> dict[str, Any]:
    base_dir = Path(__file__).resolve().parent
    module_path = base_dir / step_file
    module = _load_module(module_path)
    if not hasattr(module, "run_step"):
        raise AttributeError(f"run_step not found in {step_file}")

    if hasattr(module, "load_context"):
        module_context = module.load_context()
        module_paths = module_context.get("paths", {})
        context_paths = context.get("paths", {})
        context_paths.update(module_paths)
        context["paths"] = context_paths

    return module.run_step(context)


def run_pipeline() -> dict[str, Any]:
    logger = get_logger("000_run_pipeline")
    context = load_context()
    context["paths"]["output_dir"].mkdir(parents=True, exist_ok=True)

    env_info = bootstrap_runtime_env(context["paths"]["project_root"])
    for loaded in env_info.get("loaded_env_files", []):
        logger.info("Loaded environment variables from %s", loaded)
    injected_keys = env_info.get("injected_keys", [])
    if injected_keys:
        logger.info("Injected runtime env keys from legacy config: %s", ", ".join(injected_keys))

    executed_steps: list[dict[str, Any]] = []
    for step_file in STEP_FILES:
        logger.info("Running %s", step_file)
        started = datetime.now(timezone.utc)
        try:
            context = run_step_by_name(step_file, context)
            executed_steps.append(
                {
                    "step": step_file,
                    "status": "ok",
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as error:
            executed_steps.append(
                {
                    "step": step_file,
                    "status": "error",
                    "error": str(error),
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            break

    summary = {
        "run_id": context["run_id"],
        "executed_steps": executed_steps,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    context["paths"]["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Pipeline finished.")
    return context


if __name__ == "__main__":
    run_pipeline()
