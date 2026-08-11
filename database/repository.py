from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from config.secrets import get_mysql_password
from logging_setup import get_logger

logger = get_logger("db_repository")


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


class EnginePool:
    def __init__(self):
        self._engines: dict[str, Engine] = {}
        self._lock = threading.Lock()

    def get(self, db_url: str, workspace_id: str = "") -> Engine:
        password = _get_mysql_password(db_url, workspace_id)
        cache_key = f"{db_url}|{password or ''}"
        with self._lock:
            if cache_key not in self._engines:
                self._engines[cache_key] = _create_engine(db_url, password)
            return self._engines[cache_key]

    def clear(self):
        with self._lock:
            for engine in self._engines.values():
                engine.dispose()
            self._engines.clear()


def _get_mysql_password(db_url: str, workspace_id: str) -> str | None:
    if not db_url.startswith("mysql"):
        return None
    return get_mysql_password(workspace_id)


def _create_engine(db_url: str, password: str | None = None) -> Engine:
    logger.debug("Creating SQLAlchemy engine: %s", _mask_url(db_url))
    kwargs: dict[str, Any] = {}
    if db_url.startswith("sqlite"):
        kwargs.update({
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        })
    elif password is not None:
        kwargs["connect_args"] = {"password": password}
    return create_engine(db_url, **kwargs)


class DatabaseRepository:
    _pools: dict[tuple[str, str], EnginePool] = {}
    _pools_lock = threading.Lock()

    def __init__(self, db_url: str, workspace_id: str = ""):
        self._db_url = db_url
        self._workspace_id = workspace_id
        self._pool = self._get_pool(db_url, workspace_id)

    @classmethod
    def _get_pool(cls, db_url: str, workspace_id: str) -> EnginePool:
        key = (db_url, workspace_id)
        with cls._pools_lock:
            if key not in cls._pools:
                cls._pools[key] = EnginePool()
            return cls._pools[key]

    @contextmanager
    def session(self) -> Generator[Connection, None, None]:
        engine = self._pool.get(self._db_url, self._workspace_id)
        conn = engine.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_query(self, sql: str, limit: int = 100) -> list[dict]:
        with self.session() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows_data = []
            for row in result:
                if len(rows_data) >= limit:
                    break
                rows_data.append(dict(zip(columns, row)))
            return rows_data

    def get_all_tables(self) -> list[dict[str, Any]]:
        with self.session() as conn:
            insp = inspect(conn)
            return [{"name": name, "sql": None} for name in insp.get_table_names()]

    def get_single_table_schema(self, table: str) -> dict[str, Any]:
        with self.session() as conn:
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
                columns.append({
                    "name": col["name"],
                    "type": type_str,
                    "nullable": col.get("nullable", True),
                    "default": default_val,
                    "pk": col["name"] in pk_columns,
                })

            return {"columns": columns, "create_sql": None}

    def table_exists(self, table: str) -> bool:
        with self.session() as conn:
            insp = inspect(conn)
            return table in insp.get_table_names()

    def execute_ddl(self, sql: str) -> None:
        with self.session() as conn:
            conn.execute(text(sql))

    def dispose(self):
        self._pool.clear()
