from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Generator, Sequence

import pymysql
from dbutils.pooled_db import PooledDB
from pymysql.cursors import DictCursor

_pool_cache: dict[str, PooledDB] = {}
_pool_lock = threading.Lock()


def _pool_key(host: str, port: int, user: str, db: str) -> str:
    return f"{user}@{host}:{port}/{db}"


def _make_pool(host: str, port: int, user: str, password: str, db: str) -> PooledDB:
    return PooledDB(
        creator=pymysql,
        mincached=2,
        maxcached=5,
        maxconnections=10,
        ping=1,
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def get_pool(host: str, port: int, user: str, password: str, db: str) -> PooledDB:
    key = _pool_key(host, port, user, db)
    with _pool_lock:
        if key not in _pool_cache:
            _pool_cache[key] = _make_pool(host, port, user, password, db)
        return _pool_cache[key]


class _CursorProxy:
    """让 cursor.execute() 返回 self，支持链式调用。"""

    def __init__(self, cursor: pymysql.cursors.DictCursor) -> None:
        self._cursor = cursor

    def execute(self, sql: str, params: Any = None) -> "_CursorProxy":
        self._cursor.execute(sql, params)
        return self

    def fetchone(self) -> dict[str, Any] | None:
        return self._cursor.fetchone()

    def fetchall(self) -> Sequence[dict[str, Any]]:
        return self._cursor.fetchall()

    def fetchmany(self, size: int = 1) -> Sequence[dict[str, Any]]:
        return self._cursor.fetchmany(size)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _ConnectionWrapper:
    def __init__(self, conn: pymysql.Connection) -> None:
        self._conn = conn

    def cursor(self) -> _CursorProxy:
        return _CursorProxy(self._conn.cursor(cursor=DictCursor))

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


@contextmanager
def DBConnection(
    host: str = "127.0.0.1",
    port: int = 3306,
    user: str = "root",
    password: str = "",
    db: str = "",
) -> Generator[_ConnectionWrapper, None, None]:
    """获取一个 MySQL 连接，退出 with 块时自动 commit，异常时 rollback。"""
    pool = get_pool(host, port, user, password, db)
    conn = pool.connection()
    wrapper = _ConnectionWrapper(conn)
    try:
        yield wrapper
        wrapper.commit()
    except Exception:
        wrapper.rollback()
        raise
    finally:
        wrapper.close()


def clear_pools() -> None:
    """清空连接池缓存（切换工作区或重新配置后调用）。"""
    global _pool_cache
    with _pool_lock:
        _pool_cache.clear()
