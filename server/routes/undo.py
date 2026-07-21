from __future__ import annotations

from fastapi import APIRouter, HTTPException

from logging_setup import get_logger
from server.dependencies import require_workspace
from services.undo_service import _ensure_repo, revert_and_trim_session

logger = get_logger("routes.undo")

router = APIRouter(prefix="/api/undo", tags=["undo"])


@router.get("")
async def undo_list():
    config = require_workspace()
    logger.info("GET /api/undo workspace=%s db_url=%s", config.workspace_id, config.db_url)
    try:
        repo = _ensure_repo(config.db_url, config.workspace_id or "")
        groups = repo.list_all_groups()
        logger.info("GET /api/undo returned %s groups", len(groups))
        return {"groups": groups}
    except Exception as e:
        logger.error("GET /api/undo failed: %s", e)
        raise


@router.post("/{group_id}/revert")
async def undo_revert(group_id: int):
    config = require_workspace()
    repo = _ensure_repo(config.db_url, config.workspace_id or "")
    try:
        reverted_ids = repo.revert_to_group(group_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"reverted_group_ids": reverted_ids}


@router.delete("/{group_id}/session")
async def undo_revert_and_trim_session(group_id: int):
    config = require_workspace()
    repo = _ensure_repo(config.db_url, config.workspace_id or "")
    try:
        reverted_ids = repo.revert_to_group(group_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    trimmed = revert_and_trim_session(repo, group_id)
    return {"reverted_group_ids": reverted_ids, "session_trimmed": trimmed}
