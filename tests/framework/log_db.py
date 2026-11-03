"""Read-only access to the chat log database for SQL data-validation tests."""

import sqlite3
from pathlib import Path
from typing import Any


class LogDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        # mode=ro: validation tests must never be able to change the data they check.
        with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, params).fetchall()

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        rows = self.query(sql, params)
        return rows[0][0] if rows else None
