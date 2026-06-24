from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

import server.sessions as sessions_module
from config.settings import settings
from server.dependencies import require_workspace
from server.schemas import (
    SessionCreateResponse,
    SessionInfo,
    SessionListItem,
    SessionListResponse,
)
from server.sessions import get_session_store

logger = logging.getLogger("scriptordb.sessions")

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse)
async def create_session():
    require_workspace()
    session = get_session_store().create()
    return SessionCreateResponse(session_id=session.session_id)


@router.get("", response_model=SessionListResponse)
async def list_sessions():
    """List all active sessions (metadata only, no message bodies)."""
    require_workspace()
    store = get_session_store()
    logger.info(
        "list_sessions: store_id=%s module_store_id=%s workspace_id=%s",
        id(store),
        id(sessions_module.session_store),
        settings.workspace_id,
    )
    sessions = store.list_sessions()
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


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    require_workspace()
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfo(
        session_id=session.session_id,
        messages=session.messages,
        runs=session.runs,
        created_at=session.created_at,
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    require_workspace()
    if not get_session_store().delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}
