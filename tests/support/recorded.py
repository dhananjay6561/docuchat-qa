"""Builds a ChatService that replays recorded LLM responses, plus shared expectation checks.

Conversation, tool and regression tests use real app code (retriever, prompt, tool loop, memory)
with only the LLM replayed, so they run offline in CI and fail the same way every time.
"""

import re
from pathlib import Path
from typing import Any

from app.chat_service import ChatResult, ChatService
from app.config import Settings
from app.llm.cassette import Cassette
from app.llm.recorded_provider import RecordedProvider
from app.main import build_service

CASSETTE_DIR = Path(__file__).resolve().parent.parent / "cassettes"
ORDER_STATUSES = ("delivered", "shipped", "processing", "cancelled", "out for delivery", "returned")


def recorded_service(
    cassette_name: str, db_path: Path, tool_failure_mode: str = "none", cassette_dir: Path = CASSETTE_DIR
) -> ChatService:
    settings = Settings(
        llm_provider="recorded",
        db_path=db_path,
        tool_failure_mode=tool_failure_mode,
        tool_timeout_seconds=0.2,
        _env_file=None,
    )
    llm = RecordedProvider(Cassette(cassette_dir / f"{cassette_name}.jsonl"))
    return build_service(settings, llm)


def check(expect: dict[str, Any], result: ChatResult) -> list[str]:
    """Compare one turn against its expectations. Returns readable failures (empty = pass)."""
    answer = result.response.answer
    low = answer.lower()
    failures: list[str] = []

    if "refused" in expect and result.response.refused != expect["refused"]:
        failures.append(f"refused={result.response.refused}, expected {expect['refused']}")
    for text in expect.get("contains_all", []):
        if text.lower() not in low:
            failures.append(f"missing {text!r}")
    if expect.get("contains_any") and not any(t.lower() in low for t in expect["contains_any"]):
        failures.append(f"none of {expect['contains_any']} found")
    for text in expect.get("not_contains", []):
        if re.search(rf"\b{re.escape(text.lower())}\b", low):
            failures.append(f"must not contain {text!r}")
    if expect.get("no_order_status"):
        leaked = [s for s in ORDER_STATUSES if re.search(rf"\b{s}\b", low)]
        if leaked:
            failures.append(f"stated an order status despite a failed lookup: {leaked}")

    cited = {s.doc for s in result.response.sources}
    for doc in expect.get("sources_include", []):
        if doc not in cited:
            failures.append(f"source {doc!r} not cited (cited: {sorted(cited)})")

    called = [e.arguments.get("order_id", "").upper() for e in result.tool_events]
    if "tool_order_ids" in expect and called != [o.upper() for o in expect["tool_order_ids"]]:
        failures.append(f"tool called with {called}, expected {expect['tool_order_ids']}")
    if expect.get("no_tool") and result.tool_events:
        failures.append(f"tool should not be called, got {called}")
    return failures
