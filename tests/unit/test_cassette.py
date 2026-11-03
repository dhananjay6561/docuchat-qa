import json
from pathlib import Path

import pytest

from app.llm.base import Message
from app.llm.cassette import Cassette, CassetteMiss, request_key
from app.llm.recorded_provider import RecordedProvider
from app.tools.orders import GET_ORDER_STATUS


def test_key_ignores_dict_order() -> None:
    assert request_key({"a": 1, "b": 2}) == request_key({"b": 2, "a": 1})


def test_miss_is_recorded_once_then_replayed_after_merge(tmp_path: Path) -> None:
    cassette = Cassette(tmp_path / "c.jsonl")
    for _ in range(2):
        with pytest.raises(CassetteMiss):
            cassette.lookup({"q": "hi"})
    pending = cassette.pending_path.read_text().splitlines()
    assert len(pending) == 1  # the same request is only queued once

    key = json.loads(pending[0])["key"]
    responses = tmp_path / "r.jsonl"
    responses.write_text(json.dumps({"key": key, "response": "hello"}) + "\n")
    assert cassette.merge(responses) == 1

    assert Cassette(tmp_path / "c.jsonl").lookup({"q": "hi"}) == "hello"


def test_recorded_provider_replays_tool_calls(tmp_path: Path) -> None:
    cassette = Cassette(tmp_path / "c.jsonl")
    provider = RecordedProvider(cassette)
    messages = [Message("user", "Where is ORD-1002?")]
    with pytest.raises(CassetteMiss):
        provider.complete("sys", messages, [GET_ORDER_STATUS])

    key = json.loads(cassette.pending_path.read_text())["key"]
    recorded = {
        "text": "",
        "tool_calls": [{"name": "get_order_status", "arguments": {"order_id": "ORD-1002"}}],
    }
    responses = tmp_path / "r.jsonl"
    responses.write_text(json.dumps({"key": key, "response": recorded}) + "\n")
    cassette.merge(responses)

    response = RecordedProvider(Cassette(tmp_path / "c.jsonl")).complete("sys", messages, [GET_ORDER_STATUS])
    assert response.tool_calls[0].arguments == {"order_id": "ORD-1002"}
