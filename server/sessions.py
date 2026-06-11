from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse

from server.schemas import MessageItem

SESSION_TTL = timedelta(hours=24)


class Session:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.messages: list[MessageItem] = []
        self._model_messages: list[ModelMessage] = []
        self.created_at = datetime.utcnow()
        self.last_access = datetime.utcnow()

    def add_user_message(self, content: str) -> None:
        self.messages.append(MessageItem(role="user", content=content))
        self.last_access = datetime.utcnow()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(MessageItem(role="assistant", content=content))
        self.last_access = datetime.utcnow()

    def add_model_messages(self, new_messages: list[ModelMessage]) -> None:
        self._model_messages.extend(new_messages)

    def get_model_messages(self) -> list[ModelMessage]:
        return list(self._model_messages)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() - self.last_access > SESSION_TTL


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        session = Session()
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired:
            del self._sessions[session_id]
            return None
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        expired = [
            sid for sid, s in self._sessions.items() if s.is_expired
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)


session_store = SessionStore()
