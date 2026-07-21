from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from agents.db_agent import reset_agent_cache
from config.workspace import (
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
    WorkspaceRegistry,
    WorkspaceSettings,
)
from server.dependencies import get_config
from server.schemas import (
    ActiveWorkspaceResponse,
    MySQLConfigRequest,
    MySQLConfigResponse,
    WorkspaceActivateRequest,
    WorkspaceCreateRequest,
    WorkspaceDeleteResponse,
    WorkspaceDetail,
    WorkspaceItem,
    WorkspaceListResponse,
)
from services.mysql_service import (
    build_error_response,
    configure_mysql,
    reset_mysql_to_sqlite,
    test_connection,
)
from services.workspace_service import (
    activate_workspace as _svc_activate,
    delete_workspace_logic,
    get_legacy_sessions_summary as _svc_legacy_summary,
    import_legacy_sessions,
    reload_session_store,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


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
            mysql_host=ws_settings.mysql_host,
            mysql_port=ws_settings.mysql_port,
            mysql_user=ws_settings.mysql_user,
            mysql_db=ws_settings.mysql_db,
            mysql_password_set=ws_settings.mysql_password_set,
        )
    )


@router.get("/activate", include_in_schema=False)
async def _placeholder():
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
        mysql_host=ws_settings.mysql_host,
        mysql_port=ws_settings.mysql_port,
        mysql_user=ws_settings.mysql_user,
        mysql_db=ws_settings.mysql_db,
        mysql_password_set=ws_settings.mysql_password_set,
    )


@router.post("/{workspace_id}/activate", response_model=WorkspaceDetail)
async def activate_workspace(workspace_id: str):
    config = get_config()
    registry = WorkspaceRegistry()
    try:
        rec = registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        ws_path = _svc_activate(config, workspace_id)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
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
        mysql_host=ws_settings.mysql_host,
        mysql_port=ws_settings.mysql_port,
        mysql_user=ws_settings.mysql_user,
        mysql_db=ws_settings.mysql_db,
        mysql_password_set=ws_settings.mysql_password_set,
    )


@router.post("/activate", response_model=WorkspaceDetail)
async def activate_workspace_by_body(req: WorkspaceActivateRequest):
    if not req.workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    return await activate_workspace(req.workspace_id)


@router.delete("/{workspace_id}", response_model=WorkspaceDeleteResponse)
async def delete_workspace(workspace_id: str, delete_files: bool = False):
    config = get_config()
    try:
        delete_workspace_logic(config, workspace_id, delete_files=delete_files)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return WorkspaceDeleteResponse(ok=True, deleted_files=delete_files)


@router.get("/legacy-sessions")
async def get_legacy_sessions_summary():
    config = get_config()
    if not config.workspace_path:
        raise HTTPException(status_code=409, detail="No active workspace")
    summary = _svc_legacy_summary()
    return {"success": True, **summary}


@router.post("/{workspace_id}/import-legacy-sessions")
async def import_legacy_sessions_endpoint(workspace_id: str):
    config = get_config()
    registry = WorkspaceRegistry()
    try:
        rec = registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        result = import_legacy_sessions(rec.path)
        return {"success": True, **result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, Exception) as e:
        raise HTTPException(status_code=500, detail=f"Failed to import sessions: {str(e)}")


@router.post("/{workspace_id}/mysql-config", response_model=MySQLConfigResponse)
async def configure_mysql_endpoint(workspace_id: str, req: MySQLConfigRequest):
    config = get_config()
    registry = WorkspaceRegistry()
    try:
        rec = registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if req.test_first:
        success, error_code, msg = test_connection(
            req.host, req.port, req.user, req.password, req.db
        )
        if not success:
            return build_error_response(
                req.host, req.port, req.user, req.db, bool(req.password),
                error_code or "unknown_error", error_code or "unknown_error", msg,
            )

    return configure_mysql(rec, req.host, req.port, req.user, req.password, req.db, config)


@router.delete("/{workspace_id}/mysql-config", response_model=MySQLConfigResponse)
async def reset_mysql_config_endpoint(workspace_id: str):
    config = get_config()
    registry = WorkspaceRegistry()
    try:
        rec = registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return reset_mysql_to_sqlite(rec, config)
