from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config.settings import settings
from logging_setup import get_logger
from server.dependencies import require_workspace
from services.undo_service import _ensure_engine, revert_and_trim_session
from tools.undo_log import list_all_groups, revert_to_group

logger = get_logger("routes.undo")

router = APIRouter(prefix="/api/undo", tags=["undo"])


@router.get("")
async def undo_list():
    require_workspace()
    logger.info("GET /api/undo workspace=%s db_url=%s", settings.workspace_id, settings.db_url)
    try:
        engine = _ensure_engine()
        groups = list_all_groups(engine)
        logger.info("GET /api/undo returned %s groups", len(groups))
        return {"groups": groups}
    except Exception as e:
        logger.error("GET /api/undo failed: %s", e)
        raise


@router.post("/{group_id}/revert")
async def undo_revert(group_id: int):
    require_workspace()
    engine = _ensure_engine()
    try:
        reverted_ids = revert_to_group(engine, group_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"reverted_group_ids": reverted_ids}


@router.delete("/{group_id}/session")
async def undo_revert_and_trim_session(group_id: int):
    require_workspace()
    engine = _ensure_engine()
    try:
        reverted_ids = revert_to_group(engine, group_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    trimmed = revert_and_trim_session(engine, group_id)
    return {"reverted_group_ids": reverted_ids, "session_trimmed": trimmed}
