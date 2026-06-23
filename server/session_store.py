from __future__ import annotations

from pathlib import Path

from server.session_file_store import FileSessionStore
from server.session_model import Session, SessionStore


def create_session_store(storage_path: Path | None = None) -> SessionStore:
    """工厂函数：根据路径创建会话存储。"""
    return FileSessionStore(storage_path=storage_path)
