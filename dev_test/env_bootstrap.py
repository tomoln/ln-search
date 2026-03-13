from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _load_dotenv_files(project_root: Path) -> list[str]:
    loaded_from: list[str] = []
    try:
        from dotenv import load_dotenv
    except Exception:
        return loaded_from

    candidates = [
        project_root / ".env",
        project_root / "dev_test" / ".env",
        project_root / "dev_test" / "config" / ".env",
    ]
    for path in candidates:
        if path.exists() and load_dotenv(dotenv_path=path, override=False):
            loaded_from.append(str(path))
    return loaded_from


def _load_legacy_dev_old_config(project_root: Path) -> dict[str, str]:
    legacy_path = project_root / "dev_old" / "config.py"
    if not legacy_path.exists():
        return {}

    spec = importlib.util.spec_from_file_location("legacy_dev_old_config", legacy_path)
    if spec is None or spec.loader is None:
        return {}

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    values: dict[str, str] = {}
    if hasattr(module, "SERPER_API_KEY"):
        raw = getattr(module, "SERPER_API_KEY")
        if isinstance(raw, str) and raw.strip():
            values["SEARCH_API_SERPER_KEY"] = raw.strip()

    if hasattr(module, "BRAVE_SEARCH_API_KEY"):
        raw = getattr(module, "BRAVE_SEARCH_API_KEY")
        if isinstance(raw, str) and raw.strip():
            values["SEARCH_API_BRAVE_KEY"] = raw.strip()

    if hasattr(module, "OPENAI_API_KEY"):
        raw = getattr(module, "OPENAI_API_KEY")
        if isinstance(raw, str) and raw.strip():
            values["LLM_API_OPENAI_KEY"] = raw.strip()

    return values


def bootstrap_runtime_env(project_root: Path) -> dict[str, object]:
    loaded_env_files = _load_dotenv_files(project_root)

    injected_keys: list[str] = []
    legacy_values = _load_legacy_dev_old_config(project_root)
    for key, value in legacy_values.items():
        if not os.getenv(key):
            os.environ[key] = value
            injected_keys.append(key)

    return {
        "loaded_env_files": loaded_env_files,
        "injected_keys": injected_keys,
    }
