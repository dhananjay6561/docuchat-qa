from pathlib import Path

from app.llm.base import ToolCall
from app.tools.orders import OrderTool


def _call(order_id: str) -> ToolCall:
    return ToolCall(id="t1", name="get_order_status", arguments={"order_id": order_id})


def test_returns_known_order(tmp_path: Path) -> None:
    result = OrderTool(tmp_path / "o.db").execute(_call("ORD-1002"))
    assert result["status"] == "shipped"
    assert result["eta"] == "2026-11-06"


def test_unknown_order(tmp_path: Path) -> None:
    assert OrderTool(tmp_path / "o.db").execute(_call("ORD-9999"))["error"] == "order_not_found"


def test_invalid_order_format(tmp_path: Path) -> None:
    assert OrderTool(tmp_path / "o.db").execute(_call("12345"))["error"] == "invalid_order_id"


def test_timeout_is_returned_as_error(tmp_path: Path) -> None:
    tool = OrderTool(tmp_path / "o.db", failure_mode="timeout", timeout_s=0.1)
    assert tool.execute(_call("ORD-1002"))["error"] == "tool_timeout"


def test_backend_failure_is_returned_as_error(tmp_path: Path) -> None:
    tool = OrderTool(tmp_path / "o.db", failure_mode="error")
    assert tool.execute(_call("ORD-1002"))["error"] == "tool_failure"


def test_unknown_tool_name(tmp_path: Path) -> None:
    call = ToolCall(id="t1", name="delete_order", arguments={})
    assert OrderTool(tmp_path / "o.db").execute(call)["error"] == "unknown_tool"
