from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import Engine, Connection, create_engine, inspect, text
from sqlalchemy.pool import StaticPool

_engine_cache: dict[str, Engine] = {}
_cache_lock = threading.Lock()


def _create_engine(db_url: str) -> Engine:
    kwargs: dict[str, Any] = {}
    if db_url.startswith("sqlite"):
        kwargs.update(
            {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        )
    return create_engine(db_url, **kwargs)


def get_engine(db_url: str) -> Engine:
    with _cache_lock:
        if db_url not in _engine_cache:
            _engine_cache[db_url] = _create_engine(db_url)
        return _engine_cache[db_url]


def get_connection(db_url: str) -> Connection:
    return get_engine(db_url).connect()


def get_all_tables(db_url: str) -> list[dict[str, Any]]:
    with get_connection(db_url) as conn:
        return _get_all_tables(conn, db_url)


def get_single_table_schema(db_url: str, table: str) -> dict[str, Any]:
    with get_connection(db_url) as conn:
        return _get_single_table_schema(conn, db_url, table)


def _get_all_tables(conn: Connection, db_url: str) -> list[dict[str, Any]]:
    insp = inspect(conn)
    return [{"name": name, "sql": None} for name in insp.get_table_names()]


def _get_single_table_schema(
    conn: Connection, db_url: str, table: str
) -> dict[str, Any]:
    insp = inspect(conn)
    if table not in insp.get_table_names():
        raise ValueError(f"Table '{table}' not found")
    col_info = insp.get_columns(table)
    pk_info = insp.get_pk_constraint(table)
    pk_columns = set(pk_info.get("constrained_columns", []))

    columns = []
    for col in col_info:
        col_type = col.get("type")
        type_str = str(col_type) if col_type is not None else "TEXT"
        default_val = col.get("default")
        if default_val is not None:
            default_val = str(default_val)
        columns.append(
            {
                "name": col["name"],
                "type": type_str,
                "nullable": col.get("nullable", True),
                "default": default_val,
                "pk": col["name"] in pk_columns,
            }
        )

    return {"columns": columns, "create_sql": None}
