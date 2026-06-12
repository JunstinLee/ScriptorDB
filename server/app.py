from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config.models import (
    get_recommended_models,
    list_available_models,
    list_canonical_models,
    resolve_canonical_slug,
)
from config.settings import settings
from server.schemas import (
    CanonicalModelItem,
    CanonicalModelsResponse,
    ChatRequest,
    DefaultModelResponse,
    HealthResponse,
    ModelEntry,
    ModelsResponse,
    ModelsWithCanonicalResponse,
    SchemaResponse,
    SchemaTable,
    SessionCreateResponse,
    SessionInfo,
)
from server.sessions import session_store
from server.streaming import stream_agent_response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    session_store.cleanup_expired()


app = FastAPI(title="ScriptorDB API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health():
    try:
        model = settings.resolved_model
    except Exception:
        model = settings.llm_model or "(not configured)"
    return HealthResponse(
        status="ok",
        provider=settings.llm_provider,
        model=model,
    )


@app.post("/api/sessions", response_model=SessionCreateResponse)
async def create_session():
    session = session_store.create()
    return SessionCreateResponse(session_id=session.session_id)


@app.get("/api/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfo(
        session_id=session.session_id,
        messages=session.messages,
        created_at=session.created_at,
    )


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    if not session_store.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.add_user_message(req.prompt)

    model_messages = session.get_model_messages()

    async def generate():
        full_output = ""
        async for sse_event in stream_agent_response(
            req.prompt,
            model_messages,
            settings,
            model=req.model,
            provider=req.provider,
        ):
            if sse_event.startswith("event: metadata"):
                import json

                data_str = sse_event.split("data: ", 1)[1].strip()
                full_output = json.loads(data_str).get("full_output", "")
            yield sse_event

        if full_output:
            session.add_assistant_message(full_output)

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
    import sqlite3

    db_path = settings.db_url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        rows = cursor.fetchall()
        tables = [SchemaTable(name=name, sql=sql) for name, sql in rows]
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
    - family: 模型族（来自 canonical）
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
        family = None
        if slug:
            from config.canonical_models import get_canonical_by_slug

            c = get_canonical_by_slug(slug)
            if c:
                display_name = c.display_name
                family = c.family
        entries.append(
            ModelEntry(
                provider_specific_id=mid,
                canonical_slug=slug,
                display_name=display_name,
                family=family,
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
