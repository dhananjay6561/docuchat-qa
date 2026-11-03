"""Runs the real app in a uvicorn subprocess for browser and Newman-style tests.

Browser tests need a real HTTP server (an in-process TestClient can't serve a browser). Each server
gets its own temporary SQLite DB, so tests can inspect exactly the rows they created.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LiveServer:
    def __init__(self, llm_provider: str = "mock", **env: str) -> None:
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.db_path = Path(tempfile.mkdtemp()) / "live.db"
        self._env = {**os.environ, "LLM_PROVIDER": llm_provider, "DB_PATH": str(self.db_path), **env}
        self._process: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> "LiveServer":
        self._process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(self.port)],
            cwd=ROOT,
            env=self._env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{self.base_url}/health", timeout=1).status_code == 200:
                    return self
            except httpx.HTTPError:
                time.sleep(0.2)
        self.__exit__()
        raise RuntimeError("live server did not start within 20s")

    def __exit__(self, *exc: object) -> None:
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=10)
