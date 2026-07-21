from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import load_default_workspace, settings
from config.workspace import workspace_sessions_dir
from server.routes import api_keys, chat, files, health, history, models, schema, sessions, settings as settings_routes, undo, workspaces
from server.sessions import _DefaultSessionStore, get_session_store


def _reload_session_store(workspace_path: Path) -> None:
    import server.sessions as sessions_module
    target = workspace_sessions_dir(workspace_path)
    sessions_module.session_store = _DefaultSessionStore(storage_path=target)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    load_default_workspace()
    _app.state.config = settings
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


app.include_router(health.router)
app.include_router(workspaces.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(schema.router)
app.include_router(models.router)
app.include_router(settings_routes.router)
app.include_router(api_keys.router)
app.include_router(files.router)
app.include_router(undo.router)
app.include_router(history.router)
