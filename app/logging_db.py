"""Writes every chat exchange to SQLite for later analysis and the data-validation tests.

PII is masked here, at the single write path, so no caller can forget to do it.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.db import connect
from app.pii import mask_pii

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      TEXT NOT NULL UNIQUE,
    session_id      TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    user_message    TEXT NOT NULL,
    answer          TEXT NOT NULL,
    sources         TEXT NOT NULL,
    refused         INTEGER NOT NULL,
    tool_calls      TEXT NOT NULL,
    latency_ms      REAL NOT NULL,
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    token_count     INTEGER NOT NULL,
    estimated_cost  REAL NOT NULL,
    pii_masked      INTEGER NOT NULL,
    provider        TEXT NOT NULL
)
"""


@dataclass
class ChatRecord:
    session_id: str
    user_message: str
    answer: str
    sources: list[str]
    refused: bool
    tool_calls: list[str]
    latency_ms: float
    input_tokens: int
    output_tokens: int
    provider: str


class ChatLogger:
    def __init__(self, db_path: Path, input_cost_per_mtok: float, output_cost_per_mtok: float) -> None:
        self.db_path = db_path
        self._in_rate = input_cost_per_mtok
        self._out_rate = output_cost_per_mtok
        with connect(db_path) as conn:
            conn.execute(SCHEMA)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self._in_rate + output_tokens * self._out_rate) / 1_000_000

    def log(self, record: ChatRecord) -> str:
        message_id = str(uuid.uuid4())
        user_message, masked_q = mask_pii(record.user_message)
        answer, masked_a = mask_pii(record.answer)
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO chat_logs (message_id, session_id, timestamp, user_message, answer, "
                "sources, refused, tool_calls, latency_ms, input_tokens, output_tokens, token_count, "
                "estimated_cost, pii_masked, provider) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    message_id,
                    record.session_id,
                    datetime.now(UTC).isoformat(),
                    user_message,
                    answer,
                    json.dumps(record.sources),
                    int(record.refused),
                    json.dumps(record.tool_calls),
                    round(record.latency_ms, 2),
                    record.input_tokens,
                    record.output_tokens,
                    record.input_tokens + record.output_tokens,
                    self.estimate_cost(record.input_tokens, record.output_tokens),
                    int(masked_q or masked_a),
                    record.provider,
                ),
            )
        return message_id
