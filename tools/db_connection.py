from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import Engine, Connection, create_engine, inspect, make_url, text
from sqlalchemy.pool import StaticPool

from config.secrets import get_mysql_password

_engine_cache: dict[str, Engine] = {}
_cache_lock = threading.Lock()


def _inject_mysql_password(db_url: str, workspace_id: str | None = None) -> str:
    """对 mysql 协议 URL，从系统密钥环注入密码。"""
    if not db_url.startswith("mysql"):
        return db_url
    if workspace_id is None:
        from config.settings import settings

        workspace_id = settings.workspace_id
    password = get_mysql_password(workspace_id) if workspace_id else None
    if password is None:
        return db_url
    url = make_url(db_url)
    return str(url.set(password=password))


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


def get_engine(db_url: str, workspace_id: str | None = None) -> Engine:
    effective_url = _inject_mysql_password(db_url, workspace_id)
    with _cache_lock:
        if effective_url not in _engine_cache:
            _engine_cache[effective_url] = _create_engine(effective_url)
        return _engine_cache[effective_url]


def get_connection(db_url: str, workspace_id: str | None = None) -> Connection:
    return get_engine(db_url, workspace_id).connect()


def get_all_tables(db_url: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
    with get_connection(db_url, workspace_id) as conn:
        return _get_all_tables(conn, db_url)


def get_single_table_schema(db_url: str, table: str, workspace_id: str | None = None) -> dict[str, Any]:
    with get_connection(db_url, workspace_id) as conn:
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
