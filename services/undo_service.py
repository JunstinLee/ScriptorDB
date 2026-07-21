from __future__ import annotations

from logging_setup import get_logger
from server.sessions import get_session_store
from tools.undo_repository import UndoRepository

logger = get_logger("services.undo")


def _ensure_repo(db_url: str, workspace_id: str) -> UndoRepository:
    repo = UndoRepository(db_url, workspace_id)
    repo.ensure_tables()
    return repo


def revert_and_trim_session(repo: UndoRepository, group_id: int) -> bool:
    store = get_session_store()
    sessions = store.list_sessions()
    trimmed = False

    for grp in repo.list_all_groups():
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
