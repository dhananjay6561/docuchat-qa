"""Per-session conversation history, kept in process memory.

Only plain user/assistant text is stored. That is enough for follow-up questions and keeps the
history provider-neutral. A real deployment with several workers would move this to Redis.
"""

from collections import defaultdict
from threading import Lock

from app.llm.base import Message


class SessionMemory:
    def __init__(self, max_turns: int) -> None:
        self._max_messages = max_turns * 2  # one turn = user message + assistant reply
        self._sessions: dict[str, list[Message]] = defaultdict(list)
        self._lock = Lock()

    def history(self, session_id: str) -> list[Message]:
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def add_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        with self._lock:
            messages = self._sessions[session_id]
            messages.extend([Message("user", user_text), Message("assistant", assistant_text)])
            # Drop the oldest turns so long chats don't grow the prompt (and cost) without limit.
            del messages[: max(0, len(messages) - self._max_messages)]

    def last_user_message(self, session_id: str) -> str | None:
        users = [m.content for m in self.history(session_id) if m.role == "user"]
        return users[-1] if users else None
