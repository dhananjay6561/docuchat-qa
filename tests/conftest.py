"""Shared fixtures. Every test gets its own temp database and the offline mock LLM."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


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
