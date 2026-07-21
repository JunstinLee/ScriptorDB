from __future__ import annotations

from tools.undo_repository import UndoRepository


class UndoManager:
    def __init__(self, db_url: str, workspace_id: str):
        self._db_url = db_url
        self._workspace_id = workspace_id
        self._undo_repo = UndoRepository(db_url, workspace_id)
        self._current_group_id: int | None = None
        self._seq: int = 0

    def on_run_start(self, session_id: str, run_id: str, prompt: str) -> None:
        if not self._db_url:
            return
        self._undo_repo.ensure_tables()
        self._current_group_id = self._undo_repo.create_group(session_id, run_id, prompt)
        self._seq = 0

    def on_run_end(self) -> None:
        if self._current_group_id is None:
            return
        self._undo_repo.finalize_group(self._current_group_id)
        self._current_group_id = None
        self._seq = 0

    def record_undo(self, operation: str, table_name: str, undo_sql: str, params: dict | None) -> None:
        if self._current_group_id is None:
            return
        self._seq += 1
        self._undo_repo.add_entry(
            self._current_group_id, self._seq, operation, table_name, undo_sql, params
        )

    @property
    def current_group_id(self) -> int | None:
        return self._current_group_id

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq
