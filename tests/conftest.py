from __future__ import annotations

from pathlib import Path

import pytest

from browser import get_manager
from config.settings import Settings
from runtime.session_file_store import FileSessionStore
from tests.support.stubs import FakeKeyring


@pytest.fixture
async def cleanup_browser():
    """Reset before, destroy after each test in browser test files.

    测试结束立即 close() 销毁浏览器实例，避免可见浏览器窗口跨用例残留。
    """
    get_manager().reset()
    yield
    await get_manager().close()


@pytest.fixture
def test_settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(db_url=f"sqlite:///{db_path}")


@pytest.fixture
def store(tmp_path):
    """工作区落盘的临时 FileSessionStore。"""
    return FileSessionStore(tmp_path / "sessions")


@pytest.fixture
def fake_keyring(monkeypatch):
    """内存 keyring：config.secrets 与 config.credential_store 同时接管。"""
    import config.credential_store as credential_store
    import config.secrets as secrets

    fake = FakeKeyring()
    monkeypatch.setattr(secrets, "keyring", fake)
    monkeypatch.setattr(credential_store, "keyring", fake)
    return fake
