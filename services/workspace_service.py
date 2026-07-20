from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.db_agent import reset_agent_cache
from config.settings import load_for_workspace
from config.workspace import WorkspaceRegistry, workspace_sessions_dir
from config.workspace_paths import LEGACY_SESSIONS_FILE, LEGACY_SESSIONS_BACKUP_FILE
import server.sessions as sessions_module
from server.sessions import _DefaultSessionStore


def reload_session_store(workspace_path: Path) -> None:
    target = workspace_sessions_dir(workspace_path)
    new_store = _DefaultSessionStore(storage_path=target)
    sessions_module.session_store = new_store


def activate_workspace(config: Any, workspace_id: str) -> Path:
    registry = WorkspaceRegistry()
    rec = registry.get(workspace_id)
    load_for_workspace(config, rec.id)
    registry.set_last_active(rec.id)
    ws_path = config.workspace_path
    if ws_path is None:
        raise RuntimeError("Workspace path missing")
    reload_session_store(ws_path)
    reset_agent_cache()
    return ws_path


def delete_workspace_logic(config: Any, workspace_id: str, delete_files: bool = False) -> bool:
    registry = WorkspaceRegistry()
    registry.get(workspace_id)
    was_active = config.workspace_id == workspace_id
    registry.remove(workspace_id, delete_files=delete_files)
    if was_active:
        config.clear()
        reset_agent_cache()
    return was_active


def get_legacy_sessions_summary() -> dict:
    if not LEGACY_SESSIONS_FILE.exists():
        return {"exists": False, "count": 0}

    try:
        payload = json.loads(LEGACY_SESSIONS_FILE.read_text())
        sessions_data = payload.get("sessions", [])
        if not isinstance(sessions_data, list):
            return {"exists": True, "count": 0}

        count = len(sessions_data)
        dates = []
        for s in sessions_data:
            if isinstance(s, dict):
                created = s.get("created_at")
                if isinstance(created, str):
                    try:
                        dates.append(datetime.fromisoformat(created))
                    except ValueError:
                        pass

        if dates:
            return {
                "exists": True,
                "count": count,
                "earliest": min(dates).isoformat(),
                "latest": max(dates).isoformat(),
            }
        return {"exists": True, "count": count}
    except (OSError, json.JSONDecodeError):
        return {"exists": False, "count": 0}


def import_legacy_sessions(workspace_path_str: str) -> dict:
    if not LEGACY_SESSIONS_FILE.exists():
        raise FileNotFoundError("No legacy sessions file found")

    payload = json.loads(LEGACY_SESSIONS_FILE.read_text())
    sessions_data = payload.get("sessions", [])
    if not isinstance(sessions_data, list):
        raise ValueError("Invalid sessions format")

    ws_path = Path(workspace_path_str)
    target_dir = workspace_sessions_dir(ws_path)
    target_dir.mkdir(parents=True, exist_ok=True)

    session_store = _DefaultSessionStore(storage_path=target_dir)

    for item in sessions_data:
        if not isinstance(item, dict):
            continue
        sid = item.get("session_id")
        if not isinstance(sid, str):
            continue

        from server.session_model import Session
        from server.schemas import MessageItem, StoredRun

        session = Session(session_id=sid)

        try:
            session.created_at = (
                datetime.fromisoformat(item["created_at"])
                if isinstance(item.get("created_at"), str)
                else datetime.utcnow()
            )
        except ValueError:
            session.created_at = datetime.utcnow()

        try:
            session.last_access = (
                datetime.fromisoformat(item["last_access"])
                if isinstance(item.get("last_access"), str)
                else datetime.utcnow()
            )
        except ValueError:
            session.last_access = datetime.utcnow()

        for m in item.get("messages", []):
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                try:
                    ts = (
                        datetime.fromisoformat(m["timestamp"])
                        if isinstance(m.get("timestamp"), str)
                        else session.created_at
                    )
                except ValueError:
                    ts = session.created_at
                session.messages.append(MessageItem(role=role, content=content, timestamp=ts))

        for r in item.get("runs", []):
            if isinstance(r, dict):
                try:
                    session.runs.append(StoredRun(**r))
                except Exception:
                    pass

        session_store._sessions[sid] = session
        session_store._write_session_file(session)

    session_store._write_index()

    try:
        LEGACY_SESSIONS_FILE.rename(LEGACY_SESSIONS_BACKUP_FILE)
    except OSError:
        pass

    return {"ok": True, "imported_count": len(sessions_data)}


__all__ = [
    "activate_workspace",
    "delete_workspace_logic",
    "get_legacy_sessions_summary",
    "import_legacy_sessions",
    "reload_session_store",
]
