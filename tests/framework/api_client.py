"""Thin, typed client for the DocuChat API used by every API-level test.

Wrapping the HTTP calls in one class keeps tests readable (`api.chat(...)`), puts headers and URLs
in one place, and attaches every request/response to the Allure report for debugging failures.
"""

import json
from typing import Any

import allure
import httpx


class DocuChatClient:
    def __init__(self, http: httpx.Client, api_key: str = "") -> None:
        # `http` can be a real httpx.Client or FastAPI's TestClient (same interface).
        self.http = http
        self.api_key = api_key

    def health(self) -> httpx.Response:
        return self._send("GET", "/health")

    def chat(self, session_id: str, message: str, **kwargs: Any) -> httpx.Response:
        return self._send("POST", "/chat", json={"session_id": session_id, "message": message}, **kwargs)

    def raw(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send anything, for negative tests (bad bodies, wrong methods, missing headers)."""
        return self._send(method, path, **kwargs)

    def _send(
        self, method: str, path: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> httpx.Response:
        headers = dict(headers or {})
        if self.api_key and "X-API-Key" not in headers:
            headers["X-API-Key"] = self.api_key
        response = self.http.request(method, path, headers=headers, **kwargs)
        self._attach(method, path, kwargs.get("json"), response)
        return response

    @staticmethod
    def _attach(method: str, path: str, body: Any, response: httpx.Response) -> None:
        request_text = f"{method} {path}\n{json.dumps(body, indent=2) if body is not None else ''}"
        allure.attach(
            request_text, name=f"request {method} {path}", attachment_type=allure.attachment_type.TEXT
        )
        allure.attach(
            f"HTTP {response.status_code}\n{response.text}",
            name=f"response {response.status_code}",
            attachment_type=allure.attachment_type.TEXT,
        )
