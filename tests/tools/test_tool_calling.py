"""Tool-calling behaviour: right tool, right arguments, and safe recovery when the tool fails."""

from pathlib import Path

import pytest

from tests.support.recorded import check, recorded_service

CASES = [
    ("valid-id", "none", "What's the status of order ORD-1001?",
     {"tool_order_ids": ["ORD-1001"], "contains_all": ["delivered"]}),
    ("lowercase-id", "none", "where is ord-1006",
     {"tool_order_ids": ["ORD-1006"], "contains_all": ["returned"]}),
    ("two-orders", "none", "Can you check ORD-1001 and ORD-1004 for me?",
     {"tool_order_ids": ["ORD-1001", "ORD-1004"], "contains_all": ["delivered", "cancelled"]}),
    ("bad-format", "none", "Check order ORD-12 please",
     {"no_order_status": True}),
    ("not-found", "none", "Where is ORD-9999?",
     {"tool_order_ids": ["ORD-9999"], "no_order_status": True}),
    ("no-order-id", "none", "What is the return window?",
     {"no_tool": True, "contains_all": ["30 days"]}),
    ("timeout", "timeout", "Where is ORD-1005?",
     {"no_order_status": True, "contains_any": ["couldn't", "could not", "unable", "sorry"]}),
    ("backend-error", "error", "Where is ORD-1005?",
     {"no_order_status": True, "contains_any": ["couldn't", "could not", "unable", "sorry"]}),
]  # fmt: skip


@pytest.mark.tools
@pytest.mark.llm
@pytest.mark.parametrize(("name", "failure_mode", "message", "expect"), CASES, ids=[c[0] for c in CASES])
def test_tool_calling(name: str, failure_mode: str, message: str, expect: dict, tmp_path: Path) -> None:
    service = recorded_service("tools", tmp_path / "t.db", failure_mode)
    result = service.chat_with_trace(f"tool-{name}", message)
    failures = check(expect, result)
    assert not failures, f"{failures}\nanswer: {result.response.answer}"
