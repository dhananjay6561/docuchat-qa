"""Test configuration from environment variables, so the same suite runs locally, in Docker and in CI.

BASE_URL       run against an already-running server instead of starting one
API_KEY        sent as X-API-Key when the target server requires it
LLM_PROVIDER   provider for servers the tests start themselves (default: mock)
HEADLESS       "0" to watch the browser in Playwright tests
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class TestConfig:
    base_url: str | None
    api_key: str
    llm_provider: str
    headless: bool

    @property
    def live_llm(self) -> bool:
        """True when tests talk to a real model, the only time LLM tests may be flaky."""
        return self.llm_provider == "anthropic"


@lru_cache
def get_config() -> TestConfig:
    return TestConfig(
        base_url=os.getenv("BASE_URL") or None,
        api_key=os.getenv("API_KEY", ""),
        llm_provider=os.getenv("LLM_PROVIDER", "mock"),
        headless=os.getenv("HEADLESS", "1") != "0",
    )
