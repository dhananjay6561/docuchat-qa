"""Builds the configured LLM provider. The only place that knows which adapters exist."""

from app.config import Settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.cassette import Cassette
from app.llm.mock_provider import MockProvider
from app.llm.recorded_provider import RecordedProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockProvider(latency_ms=settings.mock_latency_ms)
    if settings.llm_provider == "recorded":
        return RecordedProvider(Cassette(settings.cassette_path))
    return AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        effort=settings.llm_effort,
        max_tokens=settings.llm_max_tokens,
    )
