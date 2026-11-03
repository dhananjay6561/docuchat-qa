"""End-to-end through the HTTP API with the mock LLM: RAG, refusal, tool, memory and logging."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings


def _chat(client: TestClient, message: str, session: str = "s1") -> dict:
    response = client.post("/chat", json={"session_id": session, "message": message})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.smoke
def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["provider"] == "mock"
    assert body["chunks_indexed"] > 0


@pytest.mark.smoke
def test_answer_cites_its_source(client: TestClient) -> None:
    data = _chat(client, "How many days of paid annual leave do full-time employees get?")
    assert "24 days" in data["answer"]
    assert data["refused"] is False
    assert {s["doc"] for s in data["sources"]} == {"leave_policy"}


def test_refuses_when_docs_do_not_cover_it(client: TestClient) -> None:
    data = _chat(client, "What is the CEO's favourite football team?")
    assert data["refused"] is True
    assert data["sources"] == []


def test_order_status_uses_the_tool(client: TestClient) -> None:
    data = _chat(client, "Where is my order ORD-1002?")
    assert data["tool_calls"] == ["get_order_status"]
    assert "shipped" in data["answer"]


def test_tool_timeout_gives_recovery_message(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, tool_failure_mode="timeout")
    with TestClient(create_app(settings)) as client:
        data = _chat(client, "Status of ORD-1002 please")
    assert "couldn't check" in data["answer"]
    # The recovery message must not invent a status.
    for status in ("shipped", "delivered", "processing"):
        assert status not in data["answer"].lower()


def test_follow_up_uses_previous_question(client: TestClient) -> None:
    _chat(client, "How many days of sick leave do employees get?", session="mem")
    data = _chat(client, "Is a medical certificate needed?", session="mem")
    assert "medical certificate" in data["answer"].lower()
    assert data["sources"][0]["doc"] == "leave_policy"


def test_every_request_is_logged_with_pii_masked(client: TestClient, settings) -> None:
    message = "My email is jane@example.com, how many days of paid sick leave do employees get?"
    _chat(client, message, session="log")
    with sqlite3.connect(settings.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM chat_logs WHERE session_id = 'log'").fetchone()
    assert "jane@example.com" not in row["user_message"]
    assert "[EMAIL]" in row["user_message"]
    assert row["pii_masked"] == 1
    assert row["latency_ms"] > 0
    assert row["token_count"] == row["input_tokens"] + row["output_tokens"]
    assert row["estimated_cost"] > 0
    assert json.loads(row["sources"])


@pytest.mark.parametrize(
    "payload",
    [
        {"session_id": "s1"},
        {"message": "hi"},
        {"session_id": "", "message": "hi"},
        {"session_id": "s1", "message": ""},
        {"session_id": "s1", "message": "x" * 2001},
    ],
)
def test_invalid_requests_are_rejected(client: TestClient, payload: dict) -> None:
    assert client.post("/chat", json=payload).status_code == 422


def test_ui_is_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'data-testid="message-input"' in response.text
