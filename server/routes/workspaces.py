from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from agents.db_agent import reset_agent_cache
from config.settings import load_for_workspace, settings
from config.workspace import (
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
from server.sessions import _DefaultSessionStore, session_store

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _reload_session_store(workspace_path: Path) -> None:
    global session_store
    target = workspace_sessions_dir(workspace_path)
    session_store = _DefaultSessionStore(storage_path=target)


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
    if not req.path:
        raise HTTPException(status_code=400, detail="path is required")
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
    registry = WorkspaceRegistry()
    try:
        rec = registry.create(target, name=req.name, db_url=req.db_url)
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
