"""SQLite connection helper shared by the request log and the orders table."""

import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    # A short-lived connection per operation is simpler and thread-safe for FastAPI's worker threads.
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn
