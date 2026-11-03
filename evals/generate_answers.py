"""Stage 1: run every golden question through the real ChatService and save what happened.

The app runs exactly as in production (same retriever, prompt and tool loop). Only the LLM
provider is chosen by LLM_PROVIDER: "recorded" replays a cassette, "anthropic" calls Claude live.
"""

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.config import Settings
from app.llm.cassette import CassetteMiss
from app.main import build_service
from evals.dataset import GoldenCase

ANSWERS_PATH = Path(__file__).resolve().parent / "runs" / "answers.json"


def generate(cases: list[GoldenCase], settings: Settings) -> tuple[list[dict[str, Any]], int]:
    """Returns (answers, missing). `missing` counts cases still waiting for a recorded response."""
    with tempfile.TemporaryDirectory() as tmp:
        # A throwaway DB keeps eval traffic out of the real chat log.
        service = build_service(settings.model_copy(update={"db_path": Path(tmp) / "eval.db"}))
        answers, missing = [], 0
        for case in cases:
            try:
                # A fresh session per case so no case leaks context into another.
                result = service.chat_with_trace(f"eval-{case.id}", case.question)
            except CassetteMiss:
                missing += 1
                continue
            answers.append(
                {
                    "id": case.id,
                    "answer": result.response.answer,
                    "refused": result.response.refused,
                    "cited_docs": sorted({s.doc for s in result.response.sources}),
                    "retrieved": [{"chunk_id": h.chunk.id, "text": h.chunk.text} for h in result.retrieved],
                    "tool_events": [asdict(e) for e in result.tool_events],
                    "provider": service.llm.name,
                    "prompt_version": service.prompt.version,
                }
            )
    return answers, missing


def save(answers: list[dict[str, Any]], path: Path = ANSWERS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(answers, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
