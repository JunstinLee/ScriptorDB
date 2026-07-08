from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agents.db_agent import reset_agent_cache
from config.settings import load_for_workspace, settings
from config.workspace import (
    DEFAULT_WORKSPACES_DIR,
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
    WorkspaceRegistry,
    WorkspaceSettings,
    workspace_sessions_dir,
)
from server.dependencies import get_config
from server.schemas import (
    ActiveWorkspaceResponse,
    WorkspaceActivateRequest,
    WorkspaceCreateRequest,
    WorkspaceDeleteResponse,
    WorkspaceDetail,
    WorkspaceItem,
    WorkspaceListResponse,
)
import server.sessions as sessions_module
from server.sessions import _DefaultSessionStore
from config.workspace_paths import LEGACY_SESSIONS_FILE, LEGACY_SESSIONS_BACKUP_FILE

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _reload_session_store(workspace_path: Path) -> None:
    target = workspace_sessions_dir(workspace_path)
    new_store = _DefaultSessionStore(storage_path=target)
    sessions_module.session_store = new_store


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces():
    config = get_config()
    registry = WorkspaceRegistry()
    items = [
        WorkspaceItem(
            id=rec.id,
            name=rec.name,
            path=rec.path,
            created_at=rec.created_at,
            is_active=(rec.id == config.workspace_id),
        )
        for rec in registry.list()
    ]
    return WorkspaceListResponse(
        workspaces=items,
        active_workspace_id=config.workspace_id,
    )


@router.post("", response_model=WorkspaceItem)
async def create_workspace(req: WorkspaceCreateRequest):
    registry = WorkspaceRegistry()
    try:
        if req.path:
            target = Path(req.path).expanduser()
            if not target.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Workspace path does not exist: {target}",
                )
            if not target.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail=f"Workspace path is not a directory: {target}",
                )
            rec = registry.create(target, name=req.name, db_url=req.db_url)
        else:
            if not req.name or not req.name.strip():
                raise HTTPException(status_code=400, detail="name is required when path is not provided")
            rec = registry.create_default(req.name, db_url=req.db_url)
    except WorkspaceAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return WorkspaceItem(
        id=rec.id,
        name=rec.name,
        path=rec.path,
        created_at=rec.created_at,
        is_active=False,
    )


@router.get("/active", response_model=ActiveWorkspaceResponse)
async def get_active_workspace():
    config = get_config()
    if not config.workspace_id or not config.workspace_path:
        return ActiveWorkspaceResponse(workspace=None)
    ws_settings = WorkspaceSettings.load(
        config.workspace_path, config.workspace_id, config.workspace_name or ""
    )
    return ActiveWorkspaceResponse(
        workspace=WorkspaceDetail(
            id=config.workspace_id,
            name=config.workspace_name or "",
            path=str(config.workspace_path),
            created_at="",
            is_active=True,
            db_url=ws_settings.db_url,
            llm_provider=ws_settings.llm_provider,
            llm_model=ws_settings.llm_model,
        )
    )


@router.get("/activate", include_in_schema=False)
async def _placeholder():
    """避免与 {workspace_id} 路径冲突。实际路由在 main router。"""
    pass


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace(workspace_id: str):
    config = get_config()
    registry = WorkspaceRegistry()
    try:
        rec = registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    ws_path = Path(rec.path)
    ws_settings = WorkspaceSettings.load(ws_path, rec.id, rec.name)
    return WorkspaceDetail(
        id=rec.id,
        name=rec.name,
        path=rec.path,
        created_at=rec.created_at,
        is_active=(rec.id == config.workspace_id),
        db_url=ws_settings.db_url,
        llm_provider=ws_settings.llm_provider,
        llm_model=ws_settings.llm_model,
    )


@router.post("/{workspace_id}/activate", response_model=WorkspaceDetail)
async def activate_workspace(workspace_id: str):
    config = get_config()
    registry = WorkspaceRegistry()
    try:
        rec = registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    load_for_workspace(config, rec.id)
    registry.set_last_active(rec.id)
    ws_path = config.workspace_path
    if ws_path is None:
        raise HTTPException(status_code=500, detail="Workspace path missing")
    _reload_session_store(ws_path)
    reset_agent_cache()
    ws_settings = WorkspaceSettings.load(ws_path, config.workspace_id or rec.id, config.workspace_name or rec.name)
    return WorkspaceDetail(
        id=rec.id,
        name=rec.name,
        path=rec.path,
        created_at=rec.created_at,
        is_active=True,
        db_url=ws_settings.db_url,
        llm_provider=ws_settings.llm_provider,
        llm_model=ws_settings.llm_model,
    )


@router.post("/activate", response_model=WorkspaceDetail)
async def activate_workspace_by_body(req: WorkspaceActivateRequest):
    if not req.workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    return await activate_workspace(req.workspace_id)


@router.delete("/{workspace_id}", response_model=WorkspaceDeleteResponse)
async def delete_workspace(workspace_id: str, delete_files: bool = False):
    config = get_config()
    registry = WorkspaceRegistry()
    try:
        registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    was_active = config.workspace_id == workspace_id
    registry.remove(workspace_id, delete_files=delete_files)
    if was_active:
        config.clear()
        reset_agent_cache()
    return WorkspaceDeleteResponse(ok=True, deleted_files=delete_files)


@router.get("/legacy-sessions")
async def get_legacy_sessions_summary():
    config = get_config()
    if not config.workspace_path:
        raise HTTPException(status_code=409, detail="No active workspace")
    
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
                "latest": max(dates).isoformat()
            }
        return {"exists": True, "count": count}
    except (OSError, json.JSONDecodeError):
        return {"exists": False, "count": 0}


@router.post("/{workspace_id}/import-legacy-sessions")
async def import_legacy_sessions(workspace_id: str):
    config = get_config()
    registry = WorkspaceRegistry()
    try:
        rec = registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    if not LEGACY_SESSIONS_FILE.exists():
        raise HTTPException(status_code=404, detail="No legacy sessions file found")
    
    try:
        payload = json.loads(LEGACY_SESSIONS_FILE.read_text())
        sessions_data = payload.get("sessions", [])
        if not isinstance(sessions_data, list):
            raise HTTPException(status_code=400, detail="Invalid sessions format")
        
        ws_path = Path(rec.path)
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
                session.created_at = datetime.fromisoformat(item["created_at"]) if isinstance(item.get("created_at"), str) else datetime.utcnow()
            except ValueError:
                session.created_at = datetime.utcnow()
            
            try:
                session.last_access = datetime.fromisoformat(item["last_access"]) if isinstance(item.get("last_access"), str) else datetime.utcnow()
            except ValueError:
                session.last_access = datetime.utcnow()
            
            for m in item.get("messages", []):
                if not isinstance(m, dict):
                    continue
                role = m.get("role")
                content = m.get("content")
                if role in ("user", "assistant") and isinstance(content, str):
                    try:
                        ts = datetime.fromisoformat(m["timestamp"]) if isinstance(m.get("timestamp"), str) else session.created_at
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
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to import sessions: {str(e)}")
