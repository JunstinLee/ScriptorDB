from __future__ import annotations

from config.settings import settings
from logging_setup import get_logger
from server.sessions import get_session_store
from tools.db_connection import get_engine
from tools.undo_log import ensure_undo_tables, list_all_groups, revert_to_group

logger = get_logger("services.undo")


def _ensure_engine():
    engine = get_engine(settings.db_url, workspace_id=settings.workspace_id)
    ensure_undo_tables(engine)
    return engine


def revert_and_trim_session(engine, group_id: int) -> bool:
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

    return trimmed
