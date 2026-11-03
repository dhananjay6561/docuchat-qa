"""Browser tests for the chat UI (Playwright + Page Object Model), against a real server.

The server uses the offline mock LLM so answers are deterministic. Screenshots and traces of
failing tests are saved under test-results/ (configured in pyproject.toml).
"""

import re

import allure
import pytest
from playwright.sync_api import Page, expect

from tests.framework.base_test import BaseTest
from tests.framework.pages.chat_page import ChatPage

pytestmark = [pytest.mark.web]


@allure.feature("Chat UI")
class TestChatUI(BaseTest):
    @pytest.fixture(autouse=True)
    def _open(self, page: Page, live_server: str) -> None:
        self.chat = ChatPage(page, live_server)
        self.chat.open()

    @pytest.mark.smoke
    def test_answer_shows_cited_sources(self) -> None:
        reply = self.chat.ask("How many days of paid sick leave do employees get?")
        expect(reply).to_contain_text("10 days")
        assert any(source.startswith("leave_policy") for source in self.chat.sources_of(reply))
        assert not self.chat.is_refusal(reply)

    def test_refusal_is_labelled_and_has_no_sources(self) -> None:
        reply = self.chat.ask("What is the CEO's favourite football team?")
        assert self.chat.is_refusal(reply)
        assert self.chat.sources_of(reply) == []

    def test_follow_up_question_in_the_same_session(self) -> None:
        self.chat.ask("How many days of paid sick leave do employees get?")
        reply = self.chat.ask("Is a medical certificate needed for it?")
        expect(reply).to_contain_text("medical certificate")
        expect(self.chat.user_messages).to_have_count(2)
        expect(self.chat.assistant_messages).to_have_count(2)

    def test_order_status_via_tool(self) -> None:
        reply = self.chat.ask("Where is my order ORD-1002?")
        expect(reply).to_contain_text("shipped")

    def test_server_error_shows_banner_and_ui_recovers(self, page: Page) -> None:
        # Intercept the API call to simulate an outage without touching the server.
        page.route(
            "**/chat", lambda route: route.fulfill(status=503, body='{"detail":"LLM provider unavailable"}')
        )
        self.chat.send_without_waiting("What is the return window?")
        expect(self.chat.error_banner).to_be_visible()
        expect(self.chat.error_banner).to_contain_text("503")
        expect(self.chat.input).to_be_enabled()
        expect(self.chat.assistant_messages).to_have_count(0)

    def test_empty_message_is_not_sent(self) -> None:
        self.chat.send_without_waiting("")
        expect(self.chat.user_messages).to_have_count(0)

    def test_new_chat_clears_log_and_starts_new_session(self) -> None:
        self.chat.ask("What is the return window?")
        old_session = self.chat.session_id
        self.chat.start_new_chat()
        expect(self.chat.assistant_messages).to_have_count(0)
        assert self.chat.session_id != old_session
        assert re.fullmatch(r"web-[0-9a-f]{8}", self.chat.session_id)
