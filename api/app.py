from __future__ import annotations

import core.playwright_browsers  # noqa: F401  must precede any playwright import
import core.log_to_file  # noqa: F401  redirects stdout/stderr to logs/run_<timestamp>.log

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import load_default_workspace, settings
from config.workspace import workspace_sessions_dir
from core.logging_setup import get_logger
from api.routes import api_keys, approve, browser_cookies, browser_interact, browser_profiles, browser_state, browser_stream, chat, files, health, history, login_credentials, models, schema, sessions, settings as settings_routes, undo, workspaces
from runtime.sessions import _DefaultSessionStore, get_session_store
from services.api_key_service import check_api_key_status

logger = get_logger(__name__)

_precheck_task: asyncio.Task[None] | None = None


def _precheck_api_key() -> None:
    """Probe the configured provider's key once so the UI can warn early.

    Runs in a worker thread: `probe_key` performs a blocking HTTP request
    with a 10s timeout, which must not delay startup or the event loop.
    """
    if not settings.workspace_id:
        logger.info("API key precheck skipped: no active workspace")
        return
    try:
        result = check_api_key_status(
            settings.llm_provider, settings.workspace_id, force=True
        )
    except Exception as e:
        logger.warning("API key precheck failed: %s", e)
        return
    if result.status == "valid":
        logger.info("API key precheck passed for provider=%s", result.provider)
    else:
        logger.warning(
            "API key precheck: provider=%s status=%s error=%s",
            result.provider,
            result.status,
            result.error,
        )


def _reload_session_store(workspace_path: Path) -> None:
    import runtime.sessions as sessions_module
    target = workspace_sessions_dir(workspace_path)
    sessions_module.session_store = _DefaultSessionStore(storage_path=target)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _precheck_task
    load_default_workspace()
    _app.state.config = settings
    if settings.workspace_path is not None:
        _reload_session_store(settings.workspace_path)
    _precheck_task = asyncio.create_task(asyncio.to_thread(_precheck_api_key))
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
app.include_router(approve.router)
app.include_router(schema.router)
app.include_router(models.router)
app.include_router(settings_routes.router)
app.include_router(api_keys.router)
app.include_router(files.router)
app.include_router(undo.router)
app.include_router(history.router)
app.include_router(browser_state.router)
app.include_router(browser_interact.router)
app.include_router(browser_cookies.router)
app.include_router(browser_profiles.router)
app.include_router(browser_stream.router)
app.include_router(login_credentials.router)


_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
