from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage

from agents.db_agent import reset_agent_cache
from config.models import (
    get_recommended_models,
    list_available_models,
    list_canonical_models,
    resolve_canonical_slug,
)
from config.secrets import SUPPORTED_PROVIDERS, delete_api_key, get_api_key, save_api_key
from config.settings import load_default_workspace, settings
from config.workspace import (
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
    WorkspaceNotSelectedError,
    WorkspaceRegistry,
    WorkspaceSettings,
    workspace_sessions_dir,
)
from server.schemas import (
    ActiveWorkspaceResponse,
    ApiKeyRequest,
    ApiKeyTestResponse,
    CanonicalModelItem,
    CanonicalModelsResponse,
    ChatRequest,
    DefaultModelResponse,
    HealthResponse,
    ModelEntry,
    ModelsResponse,
    ModelsWithCanonicalResponse,
    ProviderInfo,
    SchemaColumn,
    SchemaResponse,
    SchemaTable,
    SessionCreateResponse,
    SessionInfo,
    SessionListItem,
    SessionListResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    StoredRun,
    StoredToolInvocation,
    WorkspaceActivateRequest,
    WorkspaceCreateRequest,
    WorkspaceDeleteResponse,
    WorkspaceDetail,
    WorkspaceItem,
    WorkspaceListResponse,
)
from server.sessions import SessionStore, session_store
from server.streaming import stream_agent_response


def _reload_session_store(workspace_path: Path) -> None:
    global session_store
    target = workspace_sessions_dir(workspace_path)
    session_store = SessionStore(storage_path=target)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    load_default_workspace()
    if settings.workspace_path is not None:
        _reload_session_store(settings.workspace_path)
    yield


app = FastAPI(title="ScriptorDB API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_workspace() -> None:
    if not settings.workspace_id:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "No active workspace",
                "code": "WORKSPACE_NOT_SELECTED",
            },
        )


@app.get("/api/health", response_model=HealthResponse)
async def health():
    try:
        model = settings.resolved_model if settings.workspace_id else (
            settings.llm_model or "(not configured)"
        )
    except Exception:
        model = settings.llm_model or "(not configured)"
    return HealthResponse(
        status="ok",
        provider=settings.llm_provider,
        model=model,
        workspace_id=settings.workspace_id,
        workspace_name=settings.workspace_name,
    )


@app.get("/api/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces():
    registry = WorkspaceRegistry()
    items = [
        WorkspaceItem(
            id=rec.id,
            name=rec.name,
            path=rec.path,
            created_at=rec.created_at,
            is_active=(rec.id == settings.workspace_id),
        )
        for rec in registry.list()
    ]
    return WorkspaceListResponse(
        workspaces=items,
        active_workspace_id=settings.workspace_id,
    )


@app.post("/api/workspaces", response_model=WorkspaceItem)
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


@app.get("/api/workspaces/active", response_model=ActiveWorkspaceResponse)
async def get_active_workspace():
    if not settings.workspace_id or not settings.workspace_path:
        return ActiveWorkspaceResponse(workspace=None)
    ws_settings = WorkspaceSettings.load(
        settings.workspace_path, settings.workspace_id, settings.workspace_name or ""
    )
    return ActiveWorkspaceResponse(
        workspace=WorkspaceDetail(
            id=settings.workspace_id,
            name=settings.workspace_name or "",
            path=str(settings.workspace_path),
            created_at="",
            is_active=True,
            db_url=ws_settings.db_url,
            llm_provider=ws_settings.llm_provider,
            llm_model=ws_settings.llm_model,
        )
    )


@app.get("/api/workspaces/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace(workspace_id: str):
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
        is_active=(rec.id == settings.workspace_id),
        db_url=ws_settings.db_url,
        llm_provider=ws_settings.llm_provider,
        llm_model=ws_settings.llm_model,
    )


@app.post("/api/workspaces/{workspace_id}/activate", response_model=WorkspaceDetail)
async def activate_workspace(workspace_id: str):
    registry = WorkspaceRegistry()
    try:
        rec = registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    settings.load_for_workspace(rec.id)
    registry.set_last_active(rec.id)
    ws_path = settings.workspace_path
    if ws_path is None:
        raise HTTPException(status_code=500, detail="Workspace path missing")
    _reload_session_store(ws_path)
    reset_agent_cache()
    ws_settings = WorkspaceSettings.load(ws_path, settings.workspace_id or rec.id, settings.workspace_name or rec.name)
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


@app.post("/api/workspaces/activate", response_model=WorkspaceDetail)
async def activate_workspace_by_body(req: WorkspaceActivateRequest):
    if not req.workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    return await activate_workspace(req.workspace_id)


@app.delete("/api/workspaces/{workspace_id}", response_model=WorkspaceDeleteResponse)
async def delete_workspace(workspace_id: str, delete_files: bool = False):
    registry = WorkspaceRegistry()
    try:
        registry.get(workspace_id)
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    was_active = settings.workspace_id == workspace_id
    registry.remove(workspace_id, delete_files=delete_files)
    if was_active:
        settings.clear()
        reset_agent_cache()
    return WorkspaceDeleteResponse(ok=True, deleted_files=delete_files)


@app.post("/api/sessions", response_model=SessionCreateResponse)
async def create_session():
    _require_workspace()
    session = session_store.create()
    return SessionCreateResponse(session_id=session.session_id)


@app.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions():
    """List all active sessions (metadata only, no message bodies)."""
    _require_workspace()
    sessions = session_store.list_sessions()
    items: list[SessionListItem] = []
    for s in sessions:
        title = None
        first_user = next(
            (m for m in s.messages if m.role == "user" and m.content.strip()), None
        )
        if first_user:
            cleaned = first_user.content.replace(r"\s+", " ").strip()
            title = (
                cleaned[:24] + "..." if len(cleaned) > 24 else cleaned
            )
        items.append(
            SessionListItem(
                session_id=s.session_id,
                created_at=s.created_at,
                last_access=s.last_access,
                message_count=len(s.messages),
                title=title,
            )
        )
    return SessionListResponse(sessions=items)


@app.get("/api/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    _require_workspace()
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfo(
        session_id=session.session_id,
        messages=session.messages,
        runs=session.runs,
        created_at=session.created_at,
    )


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    _require_workspace()
    if not session_store.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    _require_workspace()
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.add_user_message(req.prompt)

    model_messages = session.get_model_messages()
    run_collector: dict[str, Any] = {}
    new_messages_collector: list[ModelMessage] = []

    async def generate():
        async for sse_event in stream_agent_response(
            req.prompt,
            model_messages,
            settings,
            model=req.model,
            provider=req.provider,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
        ):
            yield sse_event

        if new_messages_collector:
            session.add_model_messages(new_messages_collector)

        if run_collector.get("status") == "completed" and run_collector.get("final_output"):
            session.add_assistant_message(run_collector["final_output"])

        if run_collector:
            run = StoredRun(
                run_id=run_collector["run_id"],
                status=run_collector["status"],
                tool_invocations=[
                    StoredToolInvocation(**inv)
                    for inv in run_collector.get("tool_invocations", [])
                ],
                final_output=run_collector.get("final_output", ""),
                started_at=run_collector["started_at"],
                ended_at=run_collector.get("ended_at"),
                error_message=run_collector.get("error_message"),
            )
            session.add_run(run)
            session_store.save()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    _require_workspace()
    import sqlite3

    db_path = settings.db_url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        rows = cursor.fetchall()
        tables: list[SchemaTable] = []
        for row in rows:
            table_name = row["name"]
            col_cursor = conn.execute(f"PRAGMA table_info('{table_name.replace(chr(39), chr(39)+chr(39))}')")
            col_rows = col_cursor.fetchall()
            columns = [
                SchemaColumn(
                    name=col["name"],
                    type=col["type"],
                    pk=bool(col["pk"]),
                    notnull=bool(col["notnull"]),
                    default_value=col["dflt_value"],
                    autoincrement=bool(col["pk"]) and col["type"].upper() in ("INTEGER", "INT", "BIGINT"),
                )
                for col in col_rows
            ]
            tables.append(SchemaTable(name=table_name, sql=row["sql"], columns=columns))
    finally:
        conn.close()
    return SchemaResponse(tables=tables)


@app.get("/api/models", response_model=ModelsResponse)
async def get_models(provider: str = ""):
    p = provider.strip() or settings.llm_provider
    try:
        models = list_available_models(p)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ModelsResponse(models=models)


@app.get("/api/models/recommended", response_model=ModelsResponse)
async def get_models_recommended(provider: str = ""):
    p = provider.strip() or settings.llm_provider
    try:
        models = get_recommended_models(p)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ModelsResponse(models=models)


@app.get("/api/models/with-canonical", response_model=ModelsWithCanonicalResponse)
async def get_models_with_canonical(provider: str = ""):
    """返回带 Canonical 信息的模型列表。

    每条记录包含：
    - provider_specific_id: provider 实际模型 ID
    - canonical_slug: 推断出的 canonical slug（可为空）
    - display_name: 用户面向的展示名（来自 canonical）
    """
    p = provider.strip() or settings.llm_provider
    try:
        ids = list_available_models(p)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    entries: list[ModelEntry] = []
    for mid in ids:
        slug = resolve_canonical_slug(p, mid)
        display_name = None
        if slug:
            from config.canonical_models import get_canonical_by_slug

            c = get_canonical_by_slug(slug)
            if c:
                display_name = c.display_name
        entries.append(
            ModelEntry(
                provider_specific_id=mid,
                canonical_slug=slug,
                display_name=display_name,
            )
        )
    return ModelsWithCanonicalResponse(models=entries)


@app.get("/api/canonical-models", response_model=CanonicalModelsResponse)
async def get_canonical_models(provider: str = ""):
    """返回 Canonical Model Registry 中的模型列表。

    - 不传 provider：返回所有 canonical 模型及其 available_providers
    - 传 provider：仅返回该 provider 有 alias 的模型，附带 provider_specific_id
    """
    p = provider.strip() or None
    items = list_canonical_models(p)
    return CanonicalModelsResponse(
        models=[CanonicalModelItem(**item) for item in items]
    )


@app.get("/api/models/default", response_model=DefaultModelResponse)
async def get_default_model(provider: str = ""):
    p = provider.strip() or settings.llm_provider
    return DefaultModelResponse(model=settings.get_default_model(p))


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings():
    providers = [
        ProviderInfo(name=name, base_url=cfg.base_url)
        for name, cfg in SUPPORTED_PROVIDERS.items()
    ]
    providers_with_keys = [
        name for name in SUPPORTED_PROVIDERS.keys()
        if get_api_key(name, settings.workspace_id)
    ]
    return SettingsResponse(
        llm_provider=settings.llm_provider,
        db_url=settings.db_url,
        llm_model=settings.llm_model,
        default_models=dict(settings.default_models),
        auto_restore_sessions=settings.auto_restore_sessions,
        providers=providers,
        providers_with_keys=providers_with_keys,
        workspace_id=settings.workspace_id,
    )


@app.post("/api/settings", response_model=SettingsResponse)
async def update_settings(req: SettingsUpdateRequest):
    _require_workspace()
    if req.llm_provider is not None:
        if req.llm_provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported provider: {req.llm_provider}"
            )
        settings.set_provider(req.llm_provider)
    if req.default_model is not None:
        provider = req.default_model_provider or settings.llm_provider
        if provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported provider: {provider}"
            )
        if not req.default_model:
            if provider in settings.default_models:
                del settings.default_models[provider]
            if provider == settings.llm_provider:
                settings.llm_model = None
        else:
            settings.set_default_model(provider, req.default_model)
    if req.auto_restore_sessions is not None:
        settings.set_auto_restore_sessions(req.auto_restore_sessions)
    return await get_settings()


@app.post("/api/settings/api-key", response_model=ApiKeyTestResponse)
async def set_api_key(req: ApiKeyRequest):
    if req.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {req.provider}"
        )
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    save_api_key(req.provider, req.api_key.strip(), settings.workspace_id)
    return ApiKeyTestResponse(ok=True)


@app.delete("/api/settings/api-key/{provider}", response_model=ApiKeyTestResponse)
async def delete_provider_key(provider: str):
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {provider}"
        )
    try:
        delete_api_key(provider, settings.workspace_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApiKeyTestResponse(ok=True)


@app.post("/api/settings/api-key/test", response_model=ApiKeyTestResponse)
async def test_api_key(req: ApiKeyRequest):
    """Test an API key by calling the provider's list-models endpoint."""
    if req.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported provider: {req.provider}"
        )
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    cfg: Any = SUPPORTED_PROVIDERS[req.provider]
    url = f"{cfg.base_url.rstrip('/')}{cfg.list_models_path}"
    headers = {"Authorization": f"Bearer {req.api_key.strip()}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return ApiKeyTestResponse(ok=False, error=str(e))
    return ApiKeyTestResponse(ok=True)
