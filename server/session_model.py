from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from server.schemas import MessageItem, StoredRun


class Session:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.messages: list[MessageItem] = []
        self.model_messages: list[ModelMessage] = []
        self.runs: list[StoredRun] = []
        self.created_at = datetime.utcnow()
        self.last_access = datetime.utcnow()

    def _rebuild_model_messages(self) -> list[ModelMessage]:
        result: list[ModelMessage] = []
        for m in self.messages:
            if m.role == "user":
                result.append(ModelRequest(parts=[UserPromptPart(content=m.content)]))
            elif m.role == "assistant":
                result.append(ModelResponse(parts=[TextPart(content=m.content)]))
        return result

    def add_user_message(self, content: str) -> None:
        self.messages.append(MessageItem(role="user", content=content))
        self.last_access = datetime.utcnow()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(MessageItem(role="assistant", content=content))
        self.last_access = datetime.utcnow()

    def add_model_messages(self, new_messages: list[ModelMessage]) -> None:
        self.model_messages.extend(new_messages)
        self.last_access = datetime.utcnow()

    def add_run(self, run: StoredRun) -> None:
        for i, r in enumerate(self.runs):
            if r.run_id == run.run_id:
                self.runs[i] = run
                self.last_access = datetime.utcnow()
                return
        self.runs.append(run)
        self.last_access = datetime.utcnow()

    def get_model_messages(self) -> list[ModelMessage]:
        if self.model_messages:
            return self.model_messages.copy()
        return self._rebuild_model_messages()


class SessionStore(ABC):
    """会话存储抽象接口。"""

    @abstractmethod
    def create(self) -> Session: ...

    @abstractmethod
    def get(self, session_id: str) -> Session | None: ...

    @abstractmethod
    def delete(self, session_id: str) -> bool: ...

    @abstractmethod
    def list_sessions(self) -> list[Session]: ...

    @abstractmethod
    def save(self) -> None: ...
