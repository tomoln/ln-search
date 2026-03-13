from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

STEP_NAME = "008_out"


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
        "extracted_records": base_dir / "io" / "output" / "007_extraction.txt",
        "selected_llm": base_dir / "io" / "tmp" / "004_selected_llm.json",
        "summary_system_prompt": base_dir / "io" / "input" / "008_summary_system_prompt.txt",
        "summary_user_prompt": base_dir / "io" / "input" / "008_summary_user_prompt.txt",
        "step_output": base_dir / "io" / "output" / "008_out.txt",
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
    return {"summary_sentence_limit": 12}


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


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


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


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _chunk_texts(texts: list[str], chunk_size: int = 5) -> list[list[str]]:
    return [texts[i : i + chunk_size] for i in range(0, len(texts), chunk_size)]


def _partial_summary(chunk: list[str], sentence_limit: int) -> str:
    merged = "\n".join(chunk)
    sentences = _split_sentences(merged)
    return " ".join(sentences[:sentence_limit])


def _final_summary(partials: list[str], sentence_limit: int) -> str:
    merged = "\n".join(partials)
    sentences = _split_sentences(merged)
    return " ".join(sentences[:sentence_limit])


def _openai_summarize(
    client: OpenAI,
    model: str,
    text: str,
    max_tokens: int,
    temperature: float,
    system_prompt: str,
    user_prompt_template: str,
) -> str:
    user_prompt = user_prompt_template
    if "{text}" in user_prompt_template:
        user_prompt = user_prompt_template.replace("{text}", text)
    else:
        user_prompt = f"{user_prompt_template}\n\n{text}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()


def run_step(context: dict[str, Any]) -> dict[str, Any]:
    logger = get_logger(STEP_NAME)
    try:
        settings = load_settings()
        paths = context["paths"]
        validate_inputs([paths["extracted_records"], paths["selected_llm"]])

        extracted_rows = read_jsonl(paths["extracted_records"])
        selected_llm = json.loads(paths["selected_llm"].read_text(encoding="utf-8"))
        sentence_limit = int(settings.get("summary_sentence_limit", 12))
        openai_cfg = settings.get("openai", {})

        texts = [row.get("extracted_text", "") for row in extracted_rows if row.get("extracted_text", "")]
        chunks = _chunk_texts(texts, chunk_size=5)

        llm_name = str(selected_llm.get("name", "")).strip().lower()
        model = selected_llm.get("model") or openai_cfg.get("model_for_summary", "gpt-4o-mini")
        key_env = selected_llm.get("key_env", "LLM_API_OPENAI_KEY")
        max_tokens = int(openai_cfg.get("max_tokens", 1200))
        temperature = float(openai_cfg.get("temperature", 0.2))
        system_prompt = read_text(paths["summary_system_prompt"]).strip() or (
            "You are a precise summarizer. Return concise Japanese summary."
        )
        user_prompt_template = read_text(paths["summary_user_prompt"]).strip() or (
            "次の本文を要約してください。出力は日本語で、重要ポイント・結論・補足情報がわかる内容にしてください。\n\n{text}"
        )

        partials: list[str] = []
        final = ""
        if llm_name == "openai":
            api_key = os.getenv(key_env, "")
            if not api_key:
                raise RuntimeError(f"Missing environment variable: {key_env}")

            client = OpenAI(api_key=api_key)
            for chunk in chunks:
                chunk_text = "\n\n".join(chunk)
                partials.append(
                    _openai_summarize(
                        client=client,
                        model=model,
                        text=chunk_text,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system_prompt=system_prompt,
                        user_prompt_template=user_prompt_template,
                    )
                )

            final = _openai_summarize(
                client=client,
                model=model,
                text="\n\n".join(partials),
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
                user_prompt_template=user_prompt_template,
            )
        else:
            partials = [_partial_summary(chunk, sentence_limit=6) for chunk in chunks]
            final = _final_summary(partials, sentence_limit=sentence_limit)

        out_text = "\n".join(
            [
                "# 008_out",
                f"generated_at: {datetime.now(timezone.utc).isoformat()}",
                f"llm: {selected_llm.get('name', '')}",
                "",
                "## 重要ポイント",
                final,
                "",
                "## 結論",
                final,
                "",
                "## 補足情報",
                f"source_documents: {len(texts)}",
                f"partial_summaries: {len(partials)}",
            ]
        )
        write_text(paths["step_output"], out_text, mode="w")
        logger.info("Summary generated from %s extracted documents.", len(texts))
        return context
    except Exception as error:  # pragma: no cover
        handle_step_error(STEP_NAME, error)
        return context


if __name__ == "__main__":
    run_step(load_context())
