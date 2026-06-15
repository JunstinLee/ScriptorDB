from __future__ import annotations

import sqlite3
from typing import Any

from config.settings import Settings


def get_connection(db_url: str) -> sqlite3.Connection:
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    raise ValueError(f"Unsupported database URL: {db_url}")


def _get_all_tables(conn: sqlite3.Connection, db_url: str) -> list[dict[str, Any]]:
    cursor = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [{"name": row["name"], "sql": row["sql"]} for row in cursor.fetchall()]


def _get_single_table_schema(
    conn: sqlite3.Connection, db_url: str, table: str
) -> dict[str, Any]:
    cursor = conn.execute(
        f"PRAGMA table_info('{table.replace(chr(39), chr(39)+chr(39))}')"
    )
    info = cursor.fetchall()
    if not info:
        raise ValueError(f"Table '{table}' not found")
    cursor2 = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    create_sql = cursor2.fetchone()
    columns = [
        {
            "name": row["name"],
            "type": row["type"],
            "nullable": not row["notnull"],
            "default": row["dflt_value"],
            "pk": bool(row["pk"]),
        }
        for row in info
    ]
    return {
        "columns": columns,
        "create_sql": create_sql["sql"] if create_sql else None,
    }
