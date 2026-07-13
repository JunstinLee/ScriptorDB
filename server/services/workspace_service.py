from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.db_agent import reset_agent_cache
from config.settings import load_for_workspace
from config.workspace import WorkspaceRegistry, workspace_sessions_dir
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
