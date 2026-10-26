from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class Message:
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class SessionManager:
    """
    In-memory session store for short-term conversation context.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self, metadata: dict[str, Any] | None = None) -> Session:
        session = Session(
            session_id=str(uuid4()),
            metadata=metadata or {},
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            raise KeyError(f"Session '{session_id}' not found.")
        return self._sessions[session_id]

    def get_or_create(self, session_id: str | None = None) -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        if session_id:
            session = Session(session_id=session_id)
            self._sessions[session_id] = session
            return session
        return self.create()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        session = self.get(session_id)
        message = Message(role=role, content=content, metadata=metadata or {})
        session.messages.append(message)
        return message

    def history(self, session_id: str, limit: int | None = None) -> list[Message]:
        messages = self.get(session_id).messages
        if limit is None:
            return list(messages)
        return list(messages[-limit:])

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


session_manager = SessionManager()
