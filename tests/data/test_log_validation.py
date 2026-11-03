"""SQL data validation of the chat log database.

A realistic mix of traffic (answers, refusals, tool calls, messages containing personal data) is
sent through the API, then the stored rows are checked with SQL, the same way a data team would
audit the production table.
"""

import json
from datetime import datetime
from pathlib import Path

import allure
import pytest

from scripts.audit_logs import audit
from tests.framework.api_client import DocuChatClient
from tests.framework.base_test import BaseTest
from tests.framework.log_db import LogDatabase

pytestmark = [pytest.mark.data]

TRAFFIC = [
    ("s1", "How many days of paid sick leave do employees get?"),
    ("s1", "Is a medical certificate needed for it?"),
    ("s2", "What is the CEO's favourite football team?"),
    ("s3", "Where is my order ORD-1002?"),
    ("s4", "My email is jane.doe@example.com, how long do refunds take?"),
    ("s5", "Call me on +91 98765 43210 about express shipping costs"),
    ("s6", "My card is 4111 1111 1111 1111, can I pay by card?"),
    ("s7", "Which countries does Lumen Home ship to?"),
    ("s7", "How much does express shipping cost?"),
]


@allure.feature("Data validation")
class TestChatLogData(BaseTest):
    @pytest.fixture(autouse=True)
    def _seed(self, api_client: DocuChatClient, settings) -> None:
        for session_id, message in TRAFFIC:
            assert api_client.chat(session_id, message).status_code == 200
        self.db = LogDatabase(Path(settings.db_path))

    def test_one_row_per_request(self) -> None:
        assert self.db.scalar("SELECT COUNT(*) FROM chat_logs") == len(TRAFFIC)

    def test_no_raw_personal_data_stored(self) -> None:
        findings = audit(self.db.db_path)
        assert findings == [], f"unmasked personal data: {findings}"

    def test_pii_flag_matches_masked_content(self) -> None:
        rows = self.db.query("SELECT user_message, answer, pii_masked FROM chat_logs")
        for row in rows:
            has_marker = any(
                m in row["user_message"] + row["answer"] for m in ("[EMAIL]", "[PHONE]", "[CARD]")
            )
            assert bool(row["pii_masked"]) == has_marker, dict(row)

    def test_answered_rows_have_sources(self) -> None:
        # A grounded answer (not a refusal, not a tool answer) must cite at least one source.
        missing = self.db.query(
            "SELECT message_id, user_message FROM chat_logs "
            "WHERE refused = 0 AND tool_calls = '[]' AND sources = '[]'"
        )
        assert missing == [], [dict(r) for r in missing]

    def test_refused_rows_have_no_sources(self) -> None:
        assert self.db.scalar("SELECT COUNT(*) FROM chat_logs WHERE refused = 1 AND sources != '[]'") == 0

    def test_metrics_columns_are_populated(self) -> None:
        bad = self.db.query(
            "SELECT message_id FROM chat_logs WHERE latency_ms <= 0 OR input_tokens <= 0 "
            "OR output_tokens <= 0 OR token_count != input_tokens + output_tokens "
            "OR estimated_cost <= 0 OR provider = ''"
        )
        assert bad == [], [dict(r) for r in bad]

    def test_no_duplicate_message_ids(self) -> None:
        dupes = self.db.query(
            "SELECT message_id, COUNT(*) AS n FROM chat_logs GROUP BY message_id HAVING n > 1"
        )
        assert dupes == []

    def test_sessions_keep_their_turn_order(self) -> None:
        rows = self.db.query("SELECT session_id, timestamp FROM chat_logs ORDER BY id")
        for session in {r["session_id"] for r in rows}:
            stamps = [datetime.fromisoformat(r["timestamp"]) for r in rows if r["session_id"] == session]
            assert stamps == sorted(stamps)
            assert all(ts.tzinfo is not None for ts in stamps), "timestamps must be timezone-aware (UTC)"

    def test_json_columns_are_valid(self) -> None:
        for row in self.db.query("SELECT sources, tool_calls FROM chat_logs"):
            assert isinstance(json.loads(row["sources"]), list)
            assert isinstance(json.loads(row["tool_calls"]), list)

    def test_tool_calls_are_logged(self) -> None:
        rows = self.db.query("SELECT tool_calls FROM chat_logs WHERE user_message LIKE '%ORD-1002%'")
        assert json.loads(rows[0]["tool_calls"]) == ["get_order_status"]
