from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, Connection, Engine, ForeignKey, Integer, MetaData, String, Table, Text, inspect, select, text

_metadata = MetaData()

_undo_groups = Table(
    "_scriptordb_undo_groups",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String(32), nullable=False),
    Column("run_id", String(32), nullable=False),
    Column("prompt_preview", String(200)),
    Column("started_at", String, nullable=False),
    Column("ended_at", String),
    Column("status", String, nullable=False, default="pending"),
    Column("sequence", Integer, nullable=False),
)

_undo_entries = Table(
    "_scriptordb_undo_entries",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("group_id", Integer, ForeignKey("_scriptordb_undo_groups.id"), nullable=False),
    Column("seq_in_group", Integer, nullable=False),
    Column("operation", String, nullable=False),
    Column("table_name", String, nullable=False),
    Column("undo_sql", String, nullable=False),
    Column("params_json", Text),
    Column("created_at", String, nullable=False),
)

_DIALECT_ADJUSTMENTS = {
    "mysql": """
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
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_undo_tables(engine: Engine) -> None:
    dialect_name = engine.dialect.name
    if dialect_name == "mysql":
        adjust = _DIALECT_ADJUSTMENTS["mysql"]
        with engine.connect() as conn:
            for stmt in adjust.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))
            conn.commit()
        return
    _metadata.create_all(engine, checkfirst=True)


def create_group(conn: Connection, session_id: str, run_id: str, prompt: str) -> int:
    seq_result = conn.execute(
        select(
            _undo_groups.c.sequence
        ).order_by(_undo_groups.c.sequence.desc()).limit(1)
    )
    max_seq_row = seq_result.fetchone()
    next_seq = (max_seq_row[0] + 1) if max_seq_row else 1

    result = conn.execute(
        _undo_groups.insert().values(
            session_id=session_id,
            run_id=run_id,
            prompt_preview=prompt[:200] if prompt else "",
            started_at=_now_iso(),
            status="pending",
            sequence=next_seq,
        )
    )
    pk = result.inserted_primary_key
    if pk is None:
        raise RuntimeError("Failed to retrieve primary key for undo group")
    return pk[0]


def finalize_group(conn: Connection, group_id: int) -> None:
    conn.execute(
        _undo_groups.update()
        .where(_undo_groups.c.id == group_id)
        .values(status="completed", ended_at=_now_iso())
    )


def add_entry(
    conn: Connection,
    group_id: int,
    seq: int,
    operation: str,
    table_name: str,
    undo_sql: str,
    params: dict | None,
) -> None:
    conn.execute(
        _undo_entries.insert().values(
            group_id=group_id,
            seq_in_group=seq,
            operation=operation,
            table_name=table_name,
            undo_sql=undo_sql,
            params_json=json.dumps(params) if params else None,
            created_at=_now_iso(),
        )
    )


def list_all_groups(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(
            select(_undo_groups).order_by(_undo_groups.c.sequence.asc())
        )
        rows = result.fetchall()
    return [
        {
            "id": row.id,
            "session_id": row.session_id,
            "run_id": row.run_id,
            "prompt_preview": row.prompt_preview,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "status": row.status,
            "sequence": row.sequence,
        }
        for row in rows
    ]


def get_entries(conn: Connection, group_id: int) -> list[dict]:
    result = conn.execute(
        select(_undo_entries)
        .where(_undo_entries.c.group_id == group_id)
        .order_by(_undo_entries.c.seq_in_group.asc())
    )
    rows = result.fetchall()
    return [
        {
            "id": row.id,
            "group_id": row.group_id,
            "seq_in_group": row.seq_in_group,
            "operation": row.operation,
            "table_name": row.table_name,
            "undo_sql": row.undo_sql,
            "params_json": row.params_json,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def revert_to_group(engine: Engine, target_group_id: int) -> list[int]:
    with engine.connect() as conn:
        target_result = conn.execute(
            select(_undo_groups.c.sequence).where(_undo_groups.c.id == target_group_id)
        )
        target_row = target_result.fetchone()
        if target_row is None:
            raise ValueError(f"Undo group {target_group_id} not found")
        target_sequence = target_row[0]

        groups_result = conn.execute(
            select(_undo_groups.c.id, _undo_groups.c.sequence)
            .where(
                _undo_groups.c.sequence > target_sequence,
                _undo_groups.c.status == "completed",
            )
            .order_by(_undo_groups.c.sequence.desc())
        )
        affected_groups = groups_result.fetchall()

        reverted_ids: list[int] = []

        for group_id, _ in affected_groups:
            entries = get_entries(conn, group_id)
            for entry in reversed(entries):
                params = json.loads(entry["params_json"]) if entry.get("params_json") else {}
                conn.execute(text(entry["undo_sql"]), params)
            conn.execute(
                _undo_groups.update()
                .where(_undo_groups.c.id == group_id)
                .values(status="reverted")
            )
            reverted_ids.append(group_id)

        conn.commit()
        return reverted_ids
