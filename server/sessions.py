from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from server.schemas import MessageItem

SESSION_TTL = timedelta(hours=24)

_SESSIONS_DIR = Path.home() / ".config" / "scriptordb"
_SESSIONS_FILE = _SESSIONS_DIR / "sessions.json"


class Session:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.messages: list[MessageItem] = []
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
        pass

    def get_model_messages(self) -> list[ModelMessage]:
        return self._rebuild_model_messages()

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() - self.last_access > SESSION_TTL


class SessionStore:
    def __init__(self, storage_path: Path | None = None):
        self._storage_path = storage_path or _SESSIONS_FILE
        self._sessions: dict[str, Session] = {}
        self._load()

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        sessions_data = payload.get("sessions", [])
        if not isinstance(sessions_data, list):
            return
        now = datetime.utcnow()
        for item in sessions_data:
            if not isinstance(item, dict):
                continue
            sid = item.get("session_id")
            if not isinstance(sid, str):
                continue
            last_access_str = item.get("last_access")
            try:
                last_access = (
                    datetime.fromisoformat(last_access_str)
                    if isinstance(last_access_str, str)
                    else now
                )
            except ValueError:
                last_access = now
            if now - last_access > SESSION_TTL:
                continue
            session = Session(session_id=sid)
            session.last_access = last_access
            try:
                created_at_str = item.get("created_at")
                session.created_at = (
                    datetime.fromisoformat(created_at_str)
                    if isinstance(created_at_str, str)
                    else now
                )
            except ValueError:
                session.created_at = now
            messages_data = item.get("messages", [])
            if isinstance(messages_data, list):
                for m in messages_data:
                    if not isinstance(m, dict):
                        continue
                    role = m.get("role")
                    content = m.get("content")
                    if role in ("user", "assistant") and isinstance(content, str):
                        timestamp = m.get("timestamp")
                        try:
                            ts = (
                                datetime.fromisoformat(timestamp)
                                if isinstance(timestamp, str)
                                else now
                            )
                        except ValueError:
                            ts = now
                        session.messages.append(
                            MessageItem(role=role, content=content, timestamp=ts)
                        )
            self._sessions[sid] = session

    def save(self) -> None:
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "created_at": s.created_at.isoformat(),
                        "last_access": s.last_access.isoformat(),
                        "messages": [
                            {
                                "role": m.role,
                                "content": m.content,
                                "timestamp": m.timestamp.isoformat(),
                            }
                            for m in s.messages
                        ],
                    }
                    for s in self._sessions.values()
                ],
            }
            self._storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        except OSError:
            pass

    def create(self) -> Session:
        session = Session()
        self._sessions[session.session_id] = session
        self.save()
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired:
            del self._sessions[session_id]
            self.save()
            return None
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self.save()
            return True
        return False

    def list_sessions(self) -> list[Session]:
        active: list[Session] = []
        expired: list[str] = []
        for sid, session in self._sessions.items():
            if session.is_expired:
                expired.append(sid)
            else:
                active.append(session)
        for sid in expired:
            del self._sessions[sid]
        if expired:
            self.save()
        active.sort(key=lambda s: s.last_access, reverse=True)
        return active

    def cleanup_expired(self) -> int:
        expired = [sid for sid, s in self._sessions.items() if s.is_expired]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            self.save()
        return len(expired)


session_store = SessionStore()
