"""The core flow: retrieve -> ask the LLM -> run tools if asked -> log -> respond."""

import re
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.llm.base import LLMProvider, Message
from app.logging_db import ChatLogger, ChatRecord
from app.memory import SessionMemory
from app.rag.retriever import Hit, Retriever
from app.schemas import ChatResponse, Source
from app.tools.orders import OrderTool

REFUSAL_MARKER = "don't have that information"
PROVIDER_DECLINED = "Sorry, I can't help with that request."
TOOL_LOOP_EXHAUSTED = "Sorry, I couldn't complete that request. Please try rephrasing it."
CITATION = re.compile(r"\[([a-z0-9_\-]+)\]")
MAX_TOOL_ROUNDS = 3  # stops a model that keeps calling tools from looping forever
SNIPPET_CHARS = 160


@dataclass
class Prompt:
    version: int
    system: str

    @classmethod
    def load(cls, path: Path) -> "Prompt":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(version=int(data["version"]), system=data["system"])


class ChatService:
    def __init__(
        self,
        llm: LLMProvider,
        retriever: Retriever,
        memory: SessionMemory,
        tools: OrderTool,
        logger: ChatLogger,
        prompt: Prompt,
        top_k: int,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.memory = memory
        self.tools = tools
        self.logger = logger
        self.prompt = prompt
        self.top_k = top_k

    def chat(self, session_id: str, message: str) -> ChatResponse:
        started = time.perf_counter()
        hits = self.retriever.search(self._retrieval_query(session_id, message), self.top_k)
        conversation = [*self.memory.history(session_id), Message("user", self._user_turn(message, hits))]

        answer, tool_names, input_tokens, output_tokens = self._run_llm(conversation)

        refused = REFUSAL_MARKER in answer.lower() or answer == PROVIDER_DECLINED
        sources = [] if refused else self._cited_sources(answer, hits)
        latency_ms = (time.perf_counter() - started) * 1000

        self.memory.add_turn(session_id, message, answer)
        self.logger.log(
            ChatRecord(
                session_id=session_id,
                user_message=message,
                answer=answer,
                sources=[s.chunk_id for s in sources],
                refused=refused,
                tool_calls=tool_names,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider=self.llm.name,
            )
        )
        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sources=sources,
            refused=refused,
            tool_calls=tool_names,
            latency_ms=round(latency_ms, 2),
        )

    def _run_llm(self, conversation: list[Message]) -> tuple[str, list[str], int, int]:
        tool_names: list[str] = []
        input_tokens = output_tokens = 0
        for _ in range(MAX_TOOL_ROUNDS):
            response = self.llm.complete(self.prompt.system, conversation, self.tools.specs)
            input_tokens += response.input_tokens
            output_tokens += response.output_tokens
            if response.refused_by_provider:
                return PROVIDER_DECLINED, tool_names, input_tokens, output_tokens
            if not response.tool_calls:
                return response.text, tool_names, input_tokens, output_tokens
            conversation.append(Message("assistant", response.text, response.tool_calls, raw=response.raw))
            for call in response.tool_calls:
                tool_names.append(call.name)
                result = self.tools.execute(call)
                conversation.append(Message("tool", self.tools.to_message(result), tool_call_id=call.id))
        return TOOL_LOOP_EXHAUSTED, tool_names, input_tokens, output_tokens

    def _retrieval_query(self, session_id: str, message: str) -> str:
        # Follow-ups like "and for contractors?" have no keywords of their own, so the previous
        # question is added to the search query to carry the topic over.
        previous = self.memory.last_user_message(session_id)
        return f"{previous} {message}" if previous else message

    @staticmethod
    def _user_turn(message: str, hits: list[Hit]) -> str:
        docs = "\n".join(f'<doc id="{h.chunk.id}">\n{h.chunk.text}\n</doc>' for h in hits)
        return f"<documents>\n{docs}\n</documents>\n\nQuestion: {message}"

    @staticmethod
    def _cited_sources(answer: str, hits: list[Hit]) -> list[Source]:
        # Only return chunks from documents the answer actually cites, so the UI never shows
        # a "source" the model didn't use.
        cited = set(CITATION.findall(answer))
        seen: set[str] = set()
        sources: list[Source] = []
        for hit in hits:
            if hit.chunk.doc in cited and hit.chunk.id not in seen:
                seen.add(hit.chunk.id)
                sources.append(
                    Source(doc=hit.chunk.doc, chunk_id=hit.chunk.id, snippet=hit.chunk.text[:SNIPPET_CHARS])
                )
        return sources
