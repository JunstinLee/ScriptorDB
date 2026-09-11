"""Q1:保存凭证后 autofill 立即填充 —— 凭证保存清 watcher 填表记忆。

`login_credential_service.save()` 写 keyring 后调用
`browser.login_watcher.clear_autofill_memory()`;本测试验证该清记忆函数
确实能重置活跃 watcher 的填表去重状态(表单未变也会重试),间接覆盖
service 接线后的端到端触发条件。monkeypatch 掉 keyring 后端。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from browser.login_form import LoginField, LoginFormInfo
from browser.login_watcher import LoginWatcher
from services import login_credential_service
from schemas.login_credential import LoginCredentialSpec, SiteStatusRequest


def _spec() -> LoginCredentialSpec:
    return LoginCredentialSpec(
        site="example.com",
        username="alice",
        password="s3cret",
    )


def _info() -> LoginFormInfo:
    return LoginFormInfo(
        url="https://example.com/login",
        is_login_page=True,
        fields=[
            LoginField(role="username", selector="#user"),
            LoginField(role="password", selector="#pass"),
        ],
    )


class _FakePage:
    """最小 Page 接口(供 watcher 常驻轮询)。"""

    def __init__(self):
        self.url = "https://example.com/login"
        self._exposed: dict[str, Any] = {}
        self._removed: list[str] = []

    async def add_init_script(self, script: str) -> None:
        pass

    async def expose_function(self, name: str, callback: Any) -> None:
        self._exposed[name] = callback

    async def remove_expose_function(self, name: str) -> None:
        self._removed.append(name)
        self._exposed.pop(name, None)

    async def title(self) -> str:
        return "Sign in"

    async def evaluate(self, expression: str) -> Any:
        return "input[type=password]" in expression


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    async def wait():
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=timeout)


@pytest.mark.asyncio
async def test_save_clears_watcher_autofill_memory(monkeypatch):
    """保存凭证(monkeypatch keyring 后端)后:表单未变的 watcher 重新触发填表候选。"""
    # 1. keyring 写读替身
    stored: dict = {}

    async def _fake_save(workspace_id: str, spec: dict) -> None:
        stored.clear()
        stored.update(spec)

    async def _fake_get(workspace_id: str, site: str) -> dict | None:
        return dict(stored) if stored else None

    monkeypatch.setattr(
        "config.credential_store.save_site_credential", _fake_save
    )
    monkeypatch.setattr(
        "config.credential_store.get_site_credential", _fake_get
    )

    # 2. 起一个 watcher(带填表候选回调),先触发一轮填表候选(保存前未配置)
    page = _FakePage()
    calls: list[Any] = []

    async def on_candidate(form: Any) -> None:
        calls.append(form)

    import browser.login_form as login_form_mod

    async def _fake_extract(p):
        return _info()

    monkeypatch.setattr(login_form_mod, "extract_login_form", _fake_extract)

    w = LoginWatcher(
        page=page,
        on_detected=lambda form: _noop(),
        on_autofill_candidate=on_candidate,
    )
    await w.start()
    await _wait_for(lambda: len(calls) >= 1)
    await asyncio.sleep(0.2)
    assert len(calls) == 1  # 表单未变:候选只触发一次

    # 4. 保存凭证(此时表单样子没变) → 记忆被清；显式触发一轮 DOM 突变
    #    驱动的检测(等价于下轮 1.5s 轮询),候选应重新触发
    resp = login_credential_service.save("ws_1", _spec())
    assert resp.configured is True
    page._exposed["__scriptordb_domChanged"]()
    await _wait_for(lambda: len(calls) >= 2)
    assert len(calls) == 2
    await w.stop()


async def _noop(*a, **k):
    return None


@pytest.mark.asyncio
async def test_save_returns_non_sensitive_status(monkeypatch):
    """保存返回非敏感状态(不含明文);monkeypatch keyring 后 save 幂等可重复。"""
    monkeypatch.setattr(
        "config.credential_store.save_site_credential",
        lambda ws, spec: None,
    )
    resp1 = login_credential_service.save("ws_1", _spec())
    resp2 = login_credential_service.save("ws_1", _spec())
    assert resp1.configured is True
    assert resp1.site == "example.com"
    assert resp1.extra_field_label is None
    assert resp2.configured is True


@pytest.mark.asyncio
async def test_site_status_after_save_reports_configured(monkeypatch):
    """保存后 site-status 返回 configured=true(经 keyring 读回)。"""
    stored: dict = {}

    def _fake_save(ws, spec):
        stored.clear()
        stored.update(spec)

    def _fake_get(ws, site):
        return dict(stored) if stored else None

    monkeypatch.setattr("config.credential_store.save_site_credential", _fake_save)
    monkeypatch.setattr("config.credential_store.get_site_credential", _fake_get)

    login_credential_service.save("ws_1", _spec())
    st = login_credential_service.site_status(
        "ws_1", SiteStatusRequest(url="https://example.com/login")
    )
    assert st.configured is True
