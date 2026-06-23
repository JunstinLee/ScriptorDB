from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from config.workspace import (
    GLOBAL_CONFIG_DIR,
    LEGACY_SESSIONS_BACKUP_FILE,
    LEGACY_SESSIONS_FILE,
)
from server.schemas import MessageItem, StoredRun
from server.session_model import Session, SessionStore

_DEFAULT_STORAGE = GLOBAL_CONFIG_DIR / "global_sessions"
_PAYLOAD_VERSION = 2
_INDEX_VERSION = 2


class FileSessionStore(SessionStore):
    """基于 JSON 文件的会话存储。"""

    def __init__(self, storage_path: Path | None = None):
        self._storage_dir = Path(storage_path) if storage_path is not None else _DEFAULT_STORAGE
        self._index_file = self._storage_dir / "_index.json"
        self._sessions: dict[str, Session] = {}
        self._ensure_dir(self._storage_dir)
        self._migrate_legacy()
        self._load()

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def _session_relpath(self, session: Session) -> str:
        created = session.created_at
        return f"{created.year:04d}/{created.month:02d}/{session.session_id}.json"

    def _session_abspath(self, session: Session) -> Path:
        return self._storage_dir / self._session_relpath(session)

    def _migrate_legacy(self) -> None:
        legacy_file = LEGACY_SESSIONS_FILE
        legacy_backup = LEGACY_SESSIONS_BACKUP_FILE
        if not legacy_file.exists():
            return
        try:
            payload = json.loads(legacy_file.read_text())
        except (OSError, json.JSONDecodeError):
            return
        sessions_data = payload.get("sessions", [])
        if not isinstance(sessions_data, list):
            return
        for item in sessions_data:
            if not isinstance(item, dict):
                continue
            sid = item.get("session_id")
            if not isinstance(sid, str):
                continue
            now = datetime.utcnow()
            try:
                created_at = datetime.fromisoformat(item["created_at"]) if isinstance(item.get("created_at"), str) else now
            except ValueError:
                created_at = now
            try:
                last_access = datetime.fromisoformat(item["last_access"]) if isinstance(item.get("last_access"), str) else now
            except ValueError:
                last_access = now
            session = Session(session_id=sid)
            session.created_at = created_at
            session.last_access = last_access
            for m in item.get("messages", []):
                if not isinstance(m, dict):
                    continue
                role = m.get("role")
                content = m.get("content")
                if role in ("user", "assistant") and isinstance(content, str):
                    try:
                        ts = datetime.fromisoformat(m["timestamp"]) if isinstance(m.get("timestamp"), str) else now
                    except ValueError:
                        ts = now
                    session.messages.append(MessageItem(role=role, content=content, timestamp=ts))
            for r in item.get("runs", []):
                if isinstance(r, dict):
                    try:
                        session.runs.append(StoredRun(**r))
                    except Exception:
                        pass
            self._write_session_file(session)
        try:
            legacy_file.rename(legacy_backup)
        except OSError:
            pass

    def _load(self) -> None:
        index = self._read_index()
        if index is not None:
            for sid, meta in index.items():
                if not isinstance(meta, dict):
                    continue
                rel = meta.get("path")
                if not isinstance(rel, str):
                    continue
                file_path = self._storage_dir / rel
                if not file_path.exists():
                    continue
                try:
                    payload = json.loads(file_path.read_text())
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                session = Session(session_id=sid)
                try:
                    created_at = datetime.fromisoformat(payload["created_at"]) if isinstance(payload.get("created_at"), str) else datetime.utcnow()
                except ValueError:
                    created_at = datetime.utcnow()
                try:
                    last_access = datetime.fromisoformat(payload["last_access"]) if isinstance(payload.get("last_access"), str) else datetime.utcnow()
                except ValueError:
                    last_access = datetime.utcnow()
                session.created_at = created_at
                session.last_access = last_access
                for m in payload.get("messages", []):
                    if not isinstance(m, dict):
                        continue
                    role = m.get("role")
                    content = m.get("content")
                    if role in ("user", "assistant") and isinstance(content, str):
                        try:
                            ts = datetime.fromisoformat(m["timestamp"]) if isinstance(m.get("timestamp"), str) else datetime.utcnow()
                        except ValueError:
                            ts = datetime.utcnow()
                        session.messages.append(MessageItem(role=role, content=content, timestamp=ts))
                for r in payload.get("runs", []):
                    if isinstance(r, dict):
                        try:
                            session.runs.append(StoredRun(**r))
                        except Exception:
                            pass
                for m in payload.get("model_messages", []):
                    if isinstance(m, dict):
                        try:
                            msg_type = m.get("type")
                            parts = m.get("parts", [])
                            if msg_type == "ModelRequest":
                                model_parts = []
                                for p in parts:
                                    if isinstance(p, dict) and p.get("type") == "UserPromptPart":
                                        model_parts.append(UserPromptPart(content=p.get("content", "")))
                                if model_parts:
                                    session.model_messages.append(ModelRequest(parts=model_parts))
                            elif msg_type == "ModelResponse":
                                model_parts = []
                                for p in parts:
                                    if isinstance(p, dict) and p.get("type") == "TextPart":
                                        model_parts.append(TextPart(content=p.get("content", "")))
                                if model_parts:
                                    session.model_messages.append(ModelResponse(parts=model_parts))
                        except Exception:
                            pass
                self._sessions[sid] = session
            return
        self._rebuild_from_disk()

    def _read_index(self) -> dict[str, dict] | None:
        if not self._index_file.exists():
            return None
        try:
            payload = json.loads(self._index_file.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        index = payload.get("index")
        if not isinstance(index, dict):
            return None
        return index

    def _rebuild_from_disk(self) -> None:
        if not self._storage_dir.exists():
            return
        for file_path in self._storage_dir.rglob("*.json"):
            if file_path == self._index_file:
                continue
            try:
                payload = json.loads(file_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            sid = payload.get("session_id")
            if not isinstance(sid, str):
                continue
            session = Session(session_id=sid)
            now = datetime.utcnow()
            try:
                session.created_at = datetime.fromisoformat(payload["created_at"]) if isinstance(payload.get("created_at"), str) else now
            except ValueError:
                session.created_at = now
            try:
                session.last_access = datetime.fromisoformat(payload["last_access"]) if isinstance(payload.get("last_access"), str) else now
            except ValueError:
                session.last_access = now
            for m in payload.get("messages", []):
                if not isinstance(m, dict):
                    continue
                role = m.get("role")
                content = m.get("content")
                if role in ("user", "assistant") and isinstance(content, str):
                    try:
                        ts = datetime.fromisoformat(m["timestamp"]) if isinstance(m.get("timestamp"), str) else now
                    except ValueError:
                        ts = now
                    session.messages.append(MessageItem(role=role, content=content, timestamp=ts))
            for r in payload.get("runs", []):
                if isinstance(r, dict):
                    try:
                        session.runs.append(StoredRun(**r))
                    except Exception:
                        pass
            for m in payload.get("model_messages", []):
                if isinstance(m, dict):
                    try:
                        msg_type = m.get("type")
                        parts = m.get("parts", [])
                        if msg_type == "ModelRequest":
                            model_parts = []
                            for p in parts:
                                if isinstance(p, dict) and p.get("type") == "UserPromptPart":
                                    model_parts.append(UserPromptPart(content=p.get("content", "")))
                            if model_parts:
                                session.model_messages.append(ModelRequest(parts=model_parts))
                        elif msg_type == "ModelResponse":
                            model_parts = []
                            for p in parts:
                                if isinstance(p, dict) and p.get("type") == "TextPart":
                                    model_parts.append(TextPart(content=p.get("content", "")))
                            if model_parts:
                                session.model_messages.append(ModelResponse(parts=model_parts))
                    except Exception:
                        pass
            self._sessions[sid] = session
        if self._sessions:
            self._write_index()

    def _write_session_file(self, session: Session) -> None:
        try:
            file_path = self._session_abspath(session)
            self._ensure_dir(file_path.parent)
            model_msgs_data = []
            for m in session.model_messages:
                if isinstance(m, ModelRequest):
                    parts_data = []
                    for p in m.parts:
                        if isinstance(p, UserPromptPart):
                            parts_data.append({"type": "UserPromptPart", "content": p.content})
                    model_msgs_data.append({"type": "ModelRequest", "parts": parts_data})
                elif isinstance(m, ModelResponse):
                    parts_data = []
                    for p in m.parts:
                        if isinstance(p, TextPart):
                            parts_data.append({"type": "TextPart", "content": p.content})
                    model_msgs_data.append({"type": "ModelResponse", "parts": parts_data})
            payload = {
                "version": _PAYLOAD_VERSION,
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "last_access": session.last_access.isoformat(),
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "timestamp": m.timestamp.isoformat(),
                    }
                    for m in session.messages
                ],
                "model_messages": model_msgs_data,
                "runs": [r.model_dump() for r in session.runs],
            }
            file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        except OSError:
            pass

    def _write_index(self) -> None:
        try:
            payload = {
                "version": _INDEX_VERSION,
                "index": {
                    s.session_id: {
                        "path": self._session_relpath(s),
                        "created_at": s.created_at.isoformat(),
                        "last_access": s.last_access.isoformat(),
                        "message_count": len(s.messages),
                    }
                    for s in self._sessions.values()
                },
            }
            self._index_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        except OSError:
            pass

    def save(self) -> None:
        for session in self._sessions.values():
            self._write_session_file(session)
        self._write_index()

    def create(self) -> Session:
        session = Session()
        self._sessions[session.session_id] = session
        self._write_session_file(session)
        self._write_index()
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        try:
            file_path = self._session_abspath(session)
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass
        self._write_index()
        return True

    def list_sessions(self) -> list[Session]:
        active = list(self._sessions.values())
        active.sort(key=lambda s: s.last_access, reverse=True)
        return active

    def cleanup_expired(self) -> None:
        """兜底存储下保留 24h 过期清理；工作区存储不做 TTL 清理。"""
