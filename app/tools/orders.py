"""The one tool the assistant can call: look up an order in a fake SQLite orders table.

`failure_mode` lets tests simulate a slow or broken backend so we can check the assistant
recovers gracefully instead of inventing an order status.
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any, Literal

from app.db import connect
from app.llm.base import ToolCall, ToolSpec

ORDER_ID_FORMAT = re.compile(r"^ORD-\d{4}$")

SEED_ORDERS = [
    ("ORD-1001", "delivered", "2026-10-20", "Lumen Hub x1"),
    ("ORD-1002", "shipped", "2026-11-06", "Lumen Bulb Color x4"),
    ("ORD-1003", "processing", "2026-11-10", "Lumen Strip 2m x2"),
    ("ORD-1004", "cancelled", "n/a", "Lumen Hub x1"),
    ("ORD-1005", "out for delivery", "2026-11-04", "Lumen Motion Sensor x2"),
    ("ORD-1006", "returned", "n/a", "Lumen Bulb White x6"),
]

GET_ORDER_STATUS = ToolSpec(
    name="get_order_status",
    description=(
        "Look up the current status and estimated delivery date of a customer order. "
        "Use only when the user gives an order ID like ORD-1234."
    ),
    parameters={
        "type": "object",
        "properties": {"order_id": {"type": "string", "description": "Order ID, format ORD-1234"}},
        "required": ["order_id"],
        "additionalProperties": False,
    },
)

FailureMode = Literal["none", "timeout", "error"]


class OrderTool:
    def __init__(self, db_path: Path, failure_mode: FailureMode = "none", timeout_s: float = 2.0) -> None:
        self.db_path = db_path
        self.failure_mode = failure_mode
        self.timeout_s = timeout_s
        self._pool = ThreadPoolExecutor(max_workers=4)
        self._init_table()

    @property
    def specs(self) -> list[ToolSpec]:
        return [GET_ORDER_STATUS]

    def execute(self, call: ToolCall) -> dict[str, Any]:
        """Run a tool call and always return a JSON-able dict, never raise.

        Errors are returned as data so the LLM can tell the user what went wrong.
        """
        if call.name != GET_ORDER_STATUS.name:
            return {"error": "unknown_tool", "detail": call.name}
        future = self._pool.submit(self.get_order_status, str(call.arguments.get("order_id", "")))
        try:
            return future.result(timeout=self.timeout_s)
        except FutureTimeout:
            return {"error": "tool_timeout", "detail": f"order lookup took longer than {self.timeout_s}s"}
        except Exception as exc:  # noqa: BLE001 - any backend failure becomes a tool error message
            return {"error": "tool_failure", "detail": str(exc)}

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        if self.failure_mode == "timeout":
            time.sleep(self.timeout_s * 2)  # slower than the executor allows
        if self.failure_mode == "error":
            raise ConnectionError("orders database unavailable")

        order_id = order_id.strip().upper()
        if not ORDER_ID_FORMAT.match(order_id):
            return {"error": "invalid_order_id", "detail": "expected format ORD-1234"}
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            return {"error": "order_not_found", "order_id": order_id}
        return dict(row)

    @staticmethod
    def to_message(result: dict[str, Any]) -> str:
        return json.dumps(result)

    def _init_table(self) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS orders ("
                "order_id TEXT PRIMARY KEY, status TEXT NOT NULL, eta TEXT NOT NULL, items TEXT NOT NULL)"
            )
            conn.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?)", SEED_ORDERS)
