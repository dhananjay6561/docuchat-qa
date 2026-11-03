"""Mobile-web tests: the chat UI in Chrome on an Android emulator, via Appium (UiAutomator2).

Skipped unless `--run-mobile` is passed, because they need an emulator and an Appium server.
Setup steps are in the README ("Mobile web tests"). Environment:

    APPIUM_URL       default http://127.0.0.1:4723
    MOBILE_BASE_URL  default http://10.0.2.2:8000  (10.0.2.2 is the host machine, seen from the emulator)
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from appium import webdriver
from appium.options.android import UiAutomator2Options

from tests.mobile.mobile_chat_page import MobileChatPage

pytestmark = [pytest.mark.mobile]

CAPABILITIES = yaml.safe_load((Path(__file__).parent / "capabilities.yaml").read_text())


@pytest.fixture(scope="module")
def driver() -> Iterator[webdriver.Remote]:
    options = UiAutomator2Options().load_capabilities(CAPABILITIES)
    session = webdriver.Remote(os.getenv("APPIUM_URL", "http://127.0.0.1:4723"), options=options)
    yield session
    session.quit()


@pytest.fixture
def chat(driver: webdriver.Remote) -> MobileChatPage:
    return MobileChatPage(driver, os.getenv("MOBILE_BASE_URL", "http://10.0.2.2:8000")).open()


def test_answer_shows_sources_on_mobile(chat: MobileChatPage) -> None:
    reply = chat.ask("How many days of paid sick leave do employees get?")
    assert "10 days" in reply.text
    assert any(source.startswith("leave_policy") for source in chat.sources_of(reply))


def test_refusal_badge_on_mobile(chat: MobileChatPage) -> None:
    reply = chat.ask("What is the CEO's favourite football team?")
    assert chat.is_refusal(reply)


def test_follow_up_keeps_context_on_mobile(chat: MobileChatPage) -> None:
    chat.start_new_chat()
    chat.ask("How many days of paid sick leave do employees get?")
    reply = chat.ask("Is a medical certificate needed for it?")
    assert "medical certificate" in reply.text.lower()


def test_layout_fits_the_phone_screen(chat: MobileChatPage) -> None:
    chat.ask("Which countries does Lumen Home ship to?")
    assert not chat.has_horizontal_overflow()


def test_new_chat_clears_the_conversation(chat: MobileChatPage) -> None:
    chat.ask("What is the return window?")
    chat.start_new_chat()
    assert chat.assistant_messages() == []
