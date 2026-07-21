from __future__ import annotations


class UndoManager:
    def __init__(self, db_url: str, workspace_id: str):
        self._db_url = db_url
        self._workspace_id = workspace_id
        self._current_group_id: int | None = None
        self._seq: int = 0

    def on_run_start(self, session_id: str, run_id: str, prompt: str) -> None:
        if not self._db_url:
            return
        from tools.db_connection import get_engine
        from tools.undo_log import create_group, ensure_undo_tables

        engine = get_engine(self._db_url, workspace_id=self._workspace_id)
        ensure_undo_tables(engine)
        with engine.connect() as conn:
            self._current_group_id = create_group(conn, session_id, run_id, prompt)
            conn.commit()
        self._seq = 0

    def on_run_end(self) -> None:
        if self._current_group_id is None:
            return
        from tools.db_connection import get_engine
        from tools.undo_log import finalize_group

        engine = get_engine(self._db_url, workspace_id=self._workspace_id)
        with engine.connect() as conn:
            finalize_group(conn, self._current_group_id)
            conn.commit()
        self._current_group_id = None
        self._seq = 0

    def record_undo(self, operation: str, table_name: str, undo_sql: str, params: dict | None) -> None:
        if self._current_group_id is None:
            return
        self._seq += 1
        from tools.db_connection import get_engine
        from tools.undo_log import add_entry

        engine = get_engine(self._db_url, workspace_id=self._workspace_id)
        with engine.connect() as conn:
            add_entry(conn, self._current_group_id, self._seq, operation, table_name, undo_sql, params)
            conn.commit()

    @property
    def current_group_id(self) -> int | None:
        return self._current_group_id

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq
