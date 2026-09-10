"""共享测试替身：内存 keyring、run registry 替身、store monkeypatch 组合。"""

from __future__ import annotations

from typing import Any


class FakeKeyring:
    """内存 keyring 后端，替代 keyring.set_password / get_password / delete_password。"""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, str]] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store.setdefault(service, {})[username] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get(service, {}).get(username)

    def delete_password(self, service: str, username: str) -> None:
        self.store.get(service, {}).pop(username, None)


class RegistryStub:
    """按 session 返回固定槽位（或 None）的 run registry 替身。"""

    def __init__(self, slot: Any | None) -> None:
        self._slot = slot

    def get(self, session_id: str) -> Any | None:
        return self._slot

    def remove(self, session_id: str, run_id: str = "") -> Any | None:
        return self._slot


class EmptyRegistry:
    """永远没有活动 run 的 registry 替身。"""

    def get(self, session_id: str) -> None:
        return None

    def remove(self, session_id: str, run_id: str = "") -> None:
        return None


def patch_store(monkeypatch: Any, store: Any) -> None:
    """把 run/会话落盘统一指向测试用 FileSessionStore。"""
    monkeypatch.setattr("runtime.sessions.get_session_store", lambda: store)
    monkeypatch.setattr("services.chat_service.get_session_store", lambda: store)
    monkeypatch.setattr(
        "runtime.approval.orchestrator.get_session_store", lambda: store
    )
