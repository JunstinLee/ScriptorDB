from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, Connection, create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from config.secrets import get_mysql_password
from logging_setup import get_logger

logger = get_logger("db_connection")


def _mask_url(db_url: str) -> str:
    if not db_url.startswith("mysql"):
        return db_url
    try:
        from sqlalchemy import make_url
        url = make_url(db_url)
        if url.password:
            return str(url.set(password="***"))
    except Exception:
        pass
    return db_url


def _get_mysql_password(db_url: str, workspace_id: str) -> str | None:
    if not db_url.startswith("mysql"):
        return None
    password = get_mysql_password(workspace_id)
    return password


def _make_engine(db_url: str, workspace_id: str = "") -> Engine:
    logger.debug("Creating SQLAlchemy engine: %s", _mask_url(db_url))
    kwargs: dict[str, Any] = {}
    if db_url.startswith("sqlite"):
        kwargs.update(
            {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        )
    else:
        password = _get_mysql_password(db_url, workspace_id)
        if password is not None:
            kwargs["connect_args"] = {"password": password}
    return create_engine(db_url, **kwargs)


def get_engine(db_url: str, workspace_id: str) -> Engine:
    logger.debug("get_engine: workspace_id=%s url=%s", workspace_id, _mask_url(db_url))
    return _make_engine(db_url, workspace_id)


def get_connection(db_url: str, workspace_id: str) -> Connection:
    logger.debug("Opening connection: %s", _mask_url(db_url))
    try:
        conn = get_engine(db_url, workspace_id).connect()
        logger.debug("Connection opened successfully")
        return conn
    except Exception as e:
        logger.error("Failed to open connection: %s", e)
        raise


def get_all_tables(db_url: str, workspace_id: str) -> list[dict[str, Any]]:
    logger.debug("Listing all tables for %s", _mask_url(db_url))
    with get_connection(db_url, workspace_id) as conn:
        return _get_all_tables(conn, db_url)


def get_single_table_schema(db_url: str, table: str, workspace_id: str) -> dict[str, Any]:
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
