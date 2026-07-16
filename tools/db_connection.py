from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import Engine, Connection, create_engine, inspect, make_url, text
from sqlalchemy.pool import StaticPool

from config.secrets import get_mysql_password
from logging_setup import get_logger

logger = get_logger("db_connection")

_engine_cache: dict[tuple[str, str | None], Engine] = {}
_cache_lock = threading.Lock()


def _mask_url(db_url: str) -> str:
    """脱敏日志中的数据库 URL 密码。"""
    if not db_url.startswith("mysql"):
        return db_url
    try:
        url = make_url(db_url)
        if url.password:
            return str(url.set(password="***"))
    except Exception:
        pass
    return db_url


def _get_mysql_password(db_url: str, workspace_id: str | None = None) -> str | None:
    """对 mysql 协议 URL，从系统密钥环读取密码。"""
    logger.debug("Read MySQL password: workspace_id=%s db_url=%s", workspace_id, _mask_url(db_url))
    if not db_url.startswith("mysql"):
        return None
    if workspace_id is None:
        from config.settings import settings

        workspace_id = settings.workspace_id
        logger.debug("Using current workspace_id=%s", workspace_id)
    password = get_mysql_password(workspace_id) if workspace_id else None
    logger.debug("MySQL password found: %s", password is not None)
    return password


def _create_engine(db_url: str, password: str | None = None) -> Engine:
    logger.debug("Creating SQLAlchemy engine: %s", _mask_url(db_url))
    kwargs: dict[str, Any] = {}
    if db_url.startswith("sqlite"):
        kwargs.update(
            {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        )
    elif password is not None:
        kwargs["connect_args"] = {"password": password}
    return create_engine(db_url, **kwargs)


def get_engine(db_url: str, workspace_id: str | None = None) -> Engine:
    password = _get_mysql_password(db_url, workspace_id)
    cache_key = (db_url, password)
    cached = cache_key in _engine_cache
    with _cache_lock:
        if cache_key not in _engine_cache:
            _engine_cache[cache_key] = _create_engine(db_url, password)
        engine = _engine_cache[cache_key]
    logger.debug("get_engine: workspace_id=%s cached=%s url=%s", workspace_id, cached, _mask_url(db_url))
    return engine


def get_connection(db_url: str, workspace_id: str | None = None) -> Connection:
    logger.debug("Opening connection: %s", _mask_url(db_url))
    try:
        conn = get_engine(db_url, workspace_id).connect()
        logger.debug("Connection opened successfully")
        return conn
    except Exception as e:
        logger.error("Failed to open connection: %s", e)
        raise


def get_all_tables(db_url: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
    logger.debug("Listing all tables for %s", _mask_url(db_url))
    with get_connection(db_url, workspace_id) as conn:
        return _get_all_tables(conn, db_url)


def get_single_table_schema(db_url: str, table: str, workspace_id: str | None = None) -> dict[str, Any]:
    logger.debug("Getting schema for table=%s db_url=%s", table, _mask_url(db_url))
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
