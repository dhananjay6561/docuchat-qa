"""Regression tests for PII that reached the chat log unmasked (cases in cases.yaml)."""

import sqlite3
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.pii import mask_pii

CASES = yaml.safe_load((Path(__file__).parent / "cases.yaml").read_text())["pii_masking"]


@pytest.mark.regression
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_masker_handles_logged_format(case: dict) -> None:
    masked, changed = mask_pii(case["message"])
    assert changed, f"{case['id']}: nothing was masked"
    for raw in case["must_not_contain"]:
        assert raw not in masked


@pytest.mark.regression
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_logged_row_has_no_raw_pii(case: dict, client: TestClient, settings) -> None:
    # End to end: the exact production message goes through the API and the stored row is checked.
    client.post("/chat", json={"session_id": case["id"], "message": case["message"]})
    with sqlite3.connect(settings.db_path) as conn:
        stored, flag = conn.execute(
            "SELECT user_message, pii_masked FROM chat_logs WHERE session_id = ?", (case["id"],)
        ).fetchone()
    for raw in case["must_not_contain"]:
        assert raw not in stored
    assert flag == 1
