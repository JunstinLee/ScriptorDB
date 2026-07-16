from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config.settings import settings
from logging_setup import get_logger
from server.dependencies import require_workspace
from server.sessions import get_session_store
from tools.db_connection import get_engine
from tools.undo_log import ensure_undo_tables, list_all_groups, revert_to_group

logger = get_logger("routes.undo")

router = APIRouter(prefix="/api/undo", tags=["undo"])


@router.get("")
async def undo_list():
    require_workspace()
    logger.info("GET /api/undo workspace=%s db_url=%s", settings.workspace_id, settings.db_url)
    try:
        engine = get_engine(settings.db_url, workspace_id=settings.workspace_id)
        ensure_undo_tables(engine)
        groups = list_all_groups(engine)
        logger.info("GET /api/undo returned %s groups", len(groups))
        return {"groups": groups}
    except Exception as e:
        logger.error("GET /api/undo failed: %s", e)
        raise


@router.post("/{group_id}/revert")
async def undo_revert(group_id: int):
    require_workspace()
    engine = get_engine(settings.db_url, workspace_id=settings.workspace_id)
    ensure_undo_tables(engine)
    try:
        reverted_ids = revert_to_group(engine, group_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"reverted_group_ids": reverted_ids}


@router.delete("/{group_id}/session")
async def undo_revert_and_trim_session(group_id: int):
    require_workspace()
    engine = get_engine(settings.db_url, workspace_id=settings.workspace_id)
    ensure_undo_tables(engine)
    try:
        reverted_ids = revert_to_group(engine, group_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    store = get_session_store()
    sessions = store.list_sessions()
    trimmed = False

    for grp in list_all_groups(engine):
        if grp["id"] == group_id:
            target_run_id = grp.get("run_id", "")
            for session in sessions:
                run_index = None
                for i, run in enumerate(session.runs):
                    if run.run_id == target_run_id:
                        run_index = i
                        break
                if run_index is not None:
                    msg_start = run_index * 2
                    if msg_start < len(session.messages):
                        del session.messages[msg_start:]
                    del session.runs[run_index:]
                    store.save()
                    trimmed = True
                if trimmed:
                    break
            break

    return {"reverted_group_ids": reverted_ids, "session_trimmed": trimmed}
