from __future__ import annotations

"""向后兼容 shim：旧的 `from server.sessions import Session, SessionStore, session_store` 仍然工作。

实际实现已拆分为：
- `server/session_model` — Session + SessionStore 抽象
- `server/session_file_store` — FileSessionStore 实现
- `server/session_store` — 工厂函数
"""

from config.workspace import (
    GLOBAL_CONFIG_DIR,
    LEGACY_SESSIONS_BACKUP_FILE,
    LEGACY_SESSIONS_FILE,
)
from server.session_file_store import FileSessionStore
from server.session_model import Session, SessionStore
from server.session_store import create_session_store


# Backwards-compat aliases: tests (and old imports) patch these module-level names.
_LEGACY_SESSIONS_FILE = LEGACY_SESSIONS_FILE
_LEGACY_BACKUP_FILE = LEGACY_SESSIONS_BACKUP_FILE
LEGACY_SESSIONS_FILE = _LEGACY_SESSIONS_FILE
LEGACY_SESSIONS_BACKUP_FILE = _LEGACY_BACKUP_FILE


# 保持向后兼容：旧代码直接实例化 SessionStore() 等价于 FileSessionStore()。
# SessionStore（ABC）保留为类型注解使用；FileSessionStore 作为可实例化的具体类。
_DefaultSessionStore = FileSessionStore


def _make_default_store() -> SessionStore:
    return _DefaultSessionStore()


session_store: SessionStore = _make_default_store()


__all__ = [
    "FileSessionStore",
    "LEGACY_SESSIONS_BACKUP_FILE",
    "LEGACY_SESSIONS_FILE",
    "Session",
    "SessionStore",
    "_DefaultSessionStore",
    "create_session_store",
    "session_store",
]
