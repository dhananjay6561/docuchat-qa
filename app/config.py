"""All runtime settings in one place, read from environment variables / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    llm_provider: Literal["anthropic", "mock", "recorded"] = "anthropic"
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high"] = "low"
    llm_max_tokens: int = 2048
    # Used when llm_provider="recorded": responses replayed from this cassette file.
    cassette_path: Path = ROOT_DIR / "evals" / "cassettes" / "app.jsonl"

    # Pricing lives in config, not code, so cost estimates stay correct when the model changes.
    input_cost_per_mtok: float = 4.0
    output_cost_per_mtok: float = 20.0

    docs_dir: Path = ROOT_DIR / "data" / "docs"
    prompt_file: Path = ROOT_DIR / "app" / "prompts" / "system.yaml"
    retrieval_top_k: int = 4
    chunk_words: int = 120

    tool_failure_mode: Literal["none", "timeout", "error"] = "none"
    tool_timeout_seconds: float = 2.0

    max_history_turns: int = 6
    db_path: Path = ROOT_DIR / "docuchat.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
