"""Provider-neutral LLM interface.

The chat service only talks to `LLMProvider`, so swapping Anthropic for another vendor (or for the
offline mock) means writing one new adapter, not touching the RAG or tool logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the tool's arguments


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # set on role="tool" messages
    # Provider-native payload for an assistant turn inside the current tool loop. Some providers
    # need their own blocks echoed back unchanged (e.g. Anthropic thinking blocks).
    raw: Any = None


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    raw: Any = None
    refused_by_provider: bool = False  # provider-side safety decline, not a "not in the docs" refusal


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        """Run one model turn. Tool execution happens in the caller, not here."""


class LLMUnavailableError(RuntimeError):
    """Raised when the provider can't be reached, so the API can return 503 instead of a 500."""
