"""Claude adapter: converts neutral messages to the Anthropic Messages API format and back."""

from typing import Any

import anthropic

from app.llm.base import LLMProvider, LLMResponse, LLMUnavailableError, Message, ToolCall, ToolSpec


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, effort: str, max_tokens: int) -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is empty. Set it in .env or use LLM_PROVIDER=mock.")
        self._client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=self._to_api_messages(messages),
                tools=[self._to_api_tool(t) for t in tools],
                # Low effort is enough for short grounded answers and keeps latency/cost down.
                output_config={"effort": self._effort},
                # If a safety classifier declines, retry on Anthropic's recommended fallback model
                # instead of failing the user's request.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as exc:
            raise LLMUnavailableError(str(exc)) from exc

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
            # thinking / fallback blocks are kept in `raw` and echoed back, never shown to users

        return LLMResponse(
            text="".join(text_parts).strip(),
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            raw=response.content,
            refused_by_provider=response.stop_reason == "refusal",
        )

    @staticmethod
    def _to_api_tool(tool: ToolSpec) -> dict[str, Any]:
        # strict=True makes Claude's arguments always match the schema, so the tool code
        # doesn't have to defend against malformed input.
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
            "strict": True,
        }

    @staticmethod
    def _to_api_messages(messages: list[Message]) -> list[dict[str, Any]]:
        api_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "user":
                api_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                # Inside a tool loop, echo the original blocks (incl. thinking) unchanged.
                content = msg.raw if msg.raw is not None else msg.content
                api_messages.append({"role": "assistant", "content": content})
            else:
                result = {"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.content}
                # All results for one assistant turn must go back in a single user message.
                last = api_messages[-1] if api_messages else None
                if last and last["role"] == "user" and isinstance(last["content"], list):
                    last["content"].append(result)
                else:
                    api_messages.append({"role": "user", "content": [result]})
        return api_messages
