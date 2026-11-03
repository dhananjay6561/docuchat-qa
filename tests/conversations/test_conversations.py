"""Multi-turn conversation scripts run against the real ChatService with recorded LLM replies."""

from pathlib import Path

import pytest
import yaml

from tests.support.recorded import check, recorded_service

SCRIPTS = yaml.safe_load((Path(__file__).parent / "scripts.yaml").read_text())["scripts"]


@pytest.mark.conversation
@pytest.mark.llm
@pytest.mark.parametrize("script", SCRIPTS, ids=[f"{s['id']}-{s['kind']}" for s in SCRIPTS])
def test_conversation(script: dict, tmp_path: Path) -> None:
    service = recorded_service("conversations", tmp_path / "c.db", script.get("tool_failure_mode", "none"))
    session = f"conv-{script['id']}"
    for number, turn in enumerate(script["turns"], start=1):
        result = service.chat_with_trace(session, turn["user"])
        failures = check(turn["expect"], result)
        assert not failures, f"turn {number} ({turn['user']!r}): {failures}\nanswer: {result.response.answer}"
