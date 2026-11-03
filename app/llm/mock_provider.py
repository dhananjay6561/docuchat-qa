"""Deterministic offline LLM.

Used by unit tests, CI and (later) load tests so they cost nothing and give the same answer every
run. It mimics the behaviour the real prompt asks for: answer from the retrieved context with a
citation, refuse when the context doesn't cover the question, and call the order tool for order IDs.
"""

import json
import math
import random
import re
import time

from app.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec
from app.rag.text import tokenize

REFUSAL = "I don't have that information in the provided documents."
ORDER_ID = re.compile(r"\bORD-\d+\b", re.IGNORECASE)
DOC_BLOCK = re.compile(r'<doc id="(?P<id>[^"]+)">\n(?P<text>.*?)\n</doc>', re.DOTALL)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, latency_ms: int = 0) -> None:
        # Load tests set a latency so the app is measured while waiting on a "slow model", not
        # answering instantly. Randomised +/-50% so requests don't move in lockstep.
        self.latency_ms = latency_ms

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        if self.latency_ms:
            time.sleep(self.latency_ms * random.uniform(0.5, 1.5) / 1000)
        last = messages[-1]
        if last.role == "tool":
            text = self._answer_from_tool(last.content)
            return self._response(system, messages, text)

        question = last.content.rsplit("Question:", 1)[-1].strip()
        order_match = ORDER_ID.search(question)
        if order_match and any(t.name == "get_order_status" for t in tools):
            call = ToolCall(
                id=f"call_{len(messages)}",
                name="get_order_status",
                arguments={"order_id": order_match.group(0).upper()},
            )
            return self._response(system, messages, "", [call])

        return self._response(system, messages, self._answer_from_context(last.content, question))

    def _answer_from_context(self, user_turn: str, question: str) -> str:
        q_tokens = set(tokenize(question))
        best: tuple[int, str, str] | None = None  # (overlap, chunk_id, sentence)
        for match in DOC_BLOCK.finditer(user_turn):
            for sentence in SENTENCE_SPLIT.split(match.group("text")):
                if sentence.startswith(("#", "(")):  # headings and title prefixes aren't answers
                    continue
                overlap = len(q_tokens & set(tokenize(sentence)))
                if best is None or overlap > best[0]:
                    best = (overlap, match.group("id"), sentence.strip())
        # Treat the context as covering the question only if it shares at least half its keywords.
        if best is None or best[0] < max(1, math.ceil(len(q_tokens) / 2)):
            return REFUSAL
        doc = best[1].split("#")[0]
        return f"{best[2]} [{doc}]"

    @staticmethod
    def _answer_from_tool(tool_output: str) -> str:
        result = json.loads(tool_output)
        if result.get("error") in ("order_not_found", "invalid_order_id"):
            return "I couldn't find an order with that ID. Please check the order number and try again."
        if "error" in result:
            # Never guess a status when the lookup failed.
            return "Sorry, I couldn't check your order status right now. Please try again in a few minutes."
        return f"Order {result['order_id']} is {result['status']}. Estimated delivery: {result['eta']}."

    @staticmethod
    def _response(
        system: str, messages: list[Message], text: str, calls: list[ToolCall] | None = None
    ) -> LLMResponse:
        # Rough 4-chars-per-token estimate so cost/token columns are populated in mock mode too.
        # The system prompt is sent on every call, so it counts towards input tokens.
        prompt_chars = len(system) + sum(len(m.content) for m in messages)
        return LLMResponse(
            text=text,
            tool_calls=calls or [],
            input_tokens=prompt_chars // 4,
            output_tokens=max(1, len(text) // 4),
        )
