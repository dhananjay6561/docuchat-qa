"""Shared fixtures and marker rules for the whole suite."""

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.framework.api_client import DocuChatClient
from tests.framework.config import get_config
from tests.framework.live_server import LiveServer
from tests.framework.openapi import OpenAPISpec


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-mobile", action="store_true", help="run Appium tests (needs an emulator)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    live_llm = get_config().live_llm
    for item in items:
        # Retries only where flakiness is expected: tests that hit a real, non-deterministic model.
        # Recorded/mock runs are deterministic, so a failure there is a real failure.
        if live_llm and item.get_closest_marker("llm"):
            item.add_marker(pytest.mark.flaky(reruns=2, reruns_delay=2))
        # Mobile tests need an Android emulator + Appium server, which CI doesn't have.
        if item.get_closest_marker("mobile") and not config.getoption("--run-mobile"):
            item.add_marker(pytest.mark.skip(reason="needs --run-mobile and a running Appium emulator"))


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        llm_provider="mock",
        db_path=tmp_path / "test.db",
        tool_timeout_seconds=0.2,
        _env_file=None,
        **overrides,
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    # Using the client as a context manager runs the app's startup (lifespan) code.
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def api_client(client: TestClient) -> Iterator[DocuChatClient]:
    """In-process by default; set BASE_URL to run the same API tests against a deployed server."""
    config = get_config()
    if config.base_url:
        with httpx.Client(base_url=config.base_url, timeout=30) as http:
            yield DocuChatClient(http, config.api_key)
    else:
        yield DocuChatClient(client)


@pytest.fixture(scope="session")
def openapi_spec() -> OpenAPISpec:
    return OpenAPISpec()


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    """Base URL of a real HTTP server (mock LLM) for browser tests, or BASE_URL if provided."""
    config = get_config()
    if config.base_url:
        yield config.base_url
        return
    with LiveServer(llm_provider=config.llm_provider) as server:
        yield server.base_url
