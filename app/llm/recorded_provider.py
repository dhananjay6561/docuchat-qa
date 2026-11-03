"""Replays recorded LLM responses from a cassette instead of calling a live model.

Used for eval runs: the answers were captured once and every later run replays them, so scores
only change when the prompt, retrieval or dataset changes, not because of model randomness.
"""

from app.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec
from app.llm.cassette import Cassette


def _serialise(msg: Message) -> dict:
    data: dict = {"role": msg.role, "content": msg.content}
    if msg.tool_calls:
        data["tool_calls"] = [{"name": c.name, "arguments": c.arguments} for c in msg.tool_calls]
    return data


class RecordedProvider(LLMProvider):
    name = "recorded"

    def __init__(self, cassette: Cassette) -> None:
        self.cassette = cassette

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        request = {
            "system": system,
            "messages": [_serialise(m) for m in messages],
            "tools": [
                {"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools
            ],
        }
        recorded = self.cassette.lookup(request)  # raises CassetteMiss if not recorded yet
        calls = [
            ToolCall(id=f"call_{len(messages)}_{i}", name=c["name"], arguments=c["arguments"])
            for i, c in enumerate(recorded.get("tool_calls", []))
        ]
        text = recorded.get("text", "")
        # Token counts use the same 4-chars-per-token estimate as the mock provider.
        prompt_chars = len(system) + sum(len(m.content) for m in messages)
        return LLMResponse(
            text=text, tool_calls=calls, input_tokens=prompt_chars // 4, output_tokens=max(1, len(text) // 4)
        )
