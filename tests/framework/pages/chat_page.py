"""Page Object for the chat UI. Tests describe what a user does; this class knows how."""

from playwright.sync_api import Locator, expect

from tests.framework.pages.base_page import BasePage


class ChatPage(BasePage):
    path = "/"

    @property
    def input(self) -> Locator:
        return self.by_test_id("message-input")

    @property
    def assistant_messages(self) -> Locator:
        return self.by_test_id("message-assistant")

    @property
    def user_messages(self) -> Locator:
        return self.by_test_id("message-user")

    @property
    def error_banner(self) -> Locator:
        return self.by_test_id("error-banner")

    @property
    def session_id(self) -> str:
        return self.by_test_id("session-id").inner_text()

    def ask(self, message: str) -> Locator:
        """Send a message and wait for the reply; returns the newest assistant message."""
        before = self.assistant_messages.count()
        self.input.fill(message)
        self.by_test_id("send-button").click()
        expect(self.assistant_messages).to_have_count(before + 1)
        return self.assistant_messages.last

    def send_without_waiting(self, message: str) -> None:
        self.input.fill(message)
        self.by_test_id("send-button").click()

    @staticmethod
    def sources_of(message: Locator) -> list[str]:
        return message.get_by_test_id("source-item").all_inner_texts()

    @staticmethod
    def is_refusal(message: Locator) -> bool:
        return message.get_by_test_id("refusal-badge").count() == 1

    def start_new_chat(self) -> None:
        self.by_test_id("new-session-button").click()
