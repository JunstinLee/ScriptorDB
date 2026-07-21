from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from tools.db_repository import DatabaseRepository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SQLITE_POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS _scriptordb_undo_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(32) NOT NULL,
    run_id VARCHAR(32) NOT NULL,
    prompt_preview VARCHAR(200),
    started_at VARCHAR(64) NOT NULL,
    ended_at VARCHAR(64),
    status VARCHAR(10) NOT NULL DEFAULT 'pending',
    sequence INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS _scriptordb_undo_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    seq_in_group INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    undo_sql TEXT NOT NULL,
    params_json TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (group_id) REFERENCES _scriptordb_undo_groups(id)
);
"""

_MYSQL_DDL = """
CREATE TABLE IF NOT EXISTS `_scriptordb_undo_groups` (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(32) NOT NULL,
    run_id VARCHAR(32) NOT NULL,
    prompt_preview VARCHAR(200),
    started_at VARCHAR(64) NOT NULL,
    ended_at VARCHAR(64),
    status VARCHAR(10) NOT NULL DEFAULT 'pending',
    sequence INTEGER NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `_scriptordb_undo_entries` (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    group_id INTEGER NOT NULL,
    seq_in_group INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    undo_sql TEXT NOT NULL,
    params_json TEXT,
    created_at VARCHAR(64) NOT NULL,
    FOREIGN KEY (group_id) REFERENCES `_scriptordb_undo_groups`(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


class UndoRepository:
    def __init__(self, db_url: str, workspace_id: str = ""):
        self._db = DatabaseRepository(db_url, workspace_id)

    @property
    def db(self) -> DatabaseRepository:
        return self._db

    def ensure_tables(self) -> None:
        with self._db.session() as conn:
            dialect = conn.dialect.name
            if dialect == "mysql":
                ddl = _MYSQL_DDL
            else:
                ddl = _SQLITE_POSTGRES_DDL
            for stmt in ddl.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))

    def create_group(self, session_id: str, run_id: str, prompt: str) -> int:
        with self._db.session() as conn:
            seq_result = conn.execute(
                text(
                    "SELECT sequence FROM _scriptordb_undo_groups "
                    "ORDER BY sequence DESC LIMIT 1"
                )
            )
            max_seq_row = seq_result.fetchone()
            next_seq = (max_seq_row[0] + 1) if max_seq_row else 1

            result = conn.execute(
                text(
                    "INSERT INTO _scriptordb_undo_groups "
                    "(session_id, run_id, prompt_preview, started_at, status, sequence) "
                    "VALUES (:session_id, :run_id, :prompt_preview, :started_at, :status, :sequence)"
                ),
                {
                    "session_id": session_id,
                    "run_id": run_id,
                    "prompt_preview": prompt[:200] if prompt else "",
                    "started_at": _now_iso(),
                    "status": "pending",
                    "sequence": next_seq,
                },
            )
            group_id = result.lastrowid
            if group_id is None:
                raise RuntimeError("Failed to retrieve primary key for undo group")
            return group_id

    def finalize_group(self, group_id: int) -> None:
        with self._db.session() as conn:
            conn.execute(
                text(
                    "UPDATE _scriptordb_undo_groups "
                    "SET status = :status, ended_at = :ended_at "
                    "WHERE id = :group_id"
                ),
                {"status": "completed", "ended_at": _now_iso(), "group_id": group_id},
            )

    def add_entry(
        self,
        group_id: int,
        seq: int,
        operation: str,
        table_name: str,
        undo_sql: str,
        params: dict | None,
    ) -> None:
        with self._db.session() as conn:
            conn.execute(
                text(
                    "INSERT INTO _scriptordb_undo_entries "
                    "(group_id, seq_in_group, operation, table_name, undo_sql, params_json, created_at) "
                    "VALUES (:group_id, :seq_in_group, :operation, :table_name, :undo_sql, :params_json, :created_at)"
                ),
                {
                    "group_id": group_id,
                    "seq_in_group": seq,
                    "operation": operation,
                    "table_name": table_name,
                    "undo_sql": undo_sql,
                    "params_json": json.dumps(params) if params else None,
                    "created_at": _now_iso(),
                },
            )

    def list_all_groups(self) -> list[dict]:
        with self._db.session() as conn:
            result = conn.execute(
                text(
                    "SELECT id, session_id, run_id, prompt_preview, "
                    "started_at, ended_at, status, sequence "
                    "FROM _scriptordb_undo_groups "
                    "ORDER BY sequence ASC"
                )
            )
            rows = result.fetchall()
        return [
            {
                "id": row[0],
                "session_id": row[1],
                "run_id": row[2],
                "prompt_preview": row[3],
                "started_at": row[4],
                "ended_at": row[5],
                "status": row[6],
                "sequence": row[7],
            }
            for row in rows
        ]

    def get_entries(self, group_id: int) -> list[dict]:
        with self._db.session() as conn:
            return self._get_entries(conn, group_id)

    def _get_entries(self, conn, group_id: int) -> list[dict]:
        result = conn.execute(
            text(
                "SELECT id, group_id, seq_in_group, operation, "
                "table_name, undo_sql, params_json, created_at "
                "FROM _scriptordb_undo_entries "
                "WHERE group_id = :group_id "
                "ORDER BY seq_in_group ASC"
            ),
            {"group_id": group_id},
        )
        rows = result.fetchall()
        return [
            {
                "id": row[0],
                "group_id": row[1],
                "seq_in_group": row[2],
                "operation": row[3],
                "table_name": row[4],
                "undo_sql": row[5],
                "params_json": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    def revert_to_group(self, target_group_id: int) -> list[int]:
        with self._db.session() as conn:
            target_result = conn.execute(
                text(
                    "SELECT sequence FROM _scriptordb_undo_groups WHERE id = :group_id"
                ),
                {"group_id": target_group_id},
            )
            target_row = target_result.fetchone()
            if target_row is None:
                raise ValueError(f"Undo group {target_group_id} not found")
            target_sequence = target_row[0]

            groups_result = conn.execute(
                text(
                    "SELECT id, sequence FROM _scriptordb_undo_groups "
                    "WHERE sequence >= :target_sequence AND status = 'completed' "
                    "ORDER BY sequence DESC"
                ),
                {"target_sequence": target_sequence},
            )
            affected_groups = groups_result.fetchall()

            reverted_ids: list[int] = []

            for group_id, _ in affected_groups:
                entries = self._get_entries(conn, group_id)
                for entry in reversed(entries):
                    params = (
                        json.loads(entry["params_json"])
                        if entry.get("params_json")
                        else {}
                    )
                    conn.execute(text(entry["undo_sql"]), params)
                conn.execute(
                    text(
                        "UPDATE _scriptordb_undo_groups "
                        "SET status = 'reverted' WHERE id = :group_id"
                    ),
                    {"group_id": group_id},
                )
                reverted_ids.append(group_id)

            return reverted_ids
