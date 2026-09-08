from __future__ import annotations

import asyncio
from typing import Any

import pytest

from runtime.runner.events import (
    human_takeover_request_event,
    login_form_detected_event,
)
from browser.login_form import LoginField, LoginFormInfo
from browser.login_watcher import LoginWatcher


def _info(url: str = "https://example.com/login") -> LoginFormInfo:
    return LoginFormInfo(
        url=url,
        is_login_page=True,
        fields=[
            LoginField(role="username", selector="#user"),
            LoginField(role="password", selector="#pass"),
        ],
    )


class _FakePage:
    """最小 Page 接口：指纹 JS / 提取 JS / observer 安装均由测试控制。"""

    def __init__(self, url: str = "https://example.com", title: str = "Home",
                 info: LoginFormInfo | None = None):
        self.url = url
        self._title = title
        self._info = info
        self._has_password = False
        self._init_scripts: list[str] = []
        self._exposed: dict[str, Any] = {}
        self._removed: list[str] = []
        self.extract_calls = 0

    async def add_init_script(self, script: str) -> None:
        self._init_scripts.append(script)

    async def expose_function(self, name: str, callback: Any) -> None:
        self._exposed[name] = callback

    async def remove_expose_function(self, name: str) -> None:
        self._removed.append(name)
        self._exposed.pop(name, None)

    async def title(self) -> str:
        return self._title

    async def evaluate(self, expression: str) -> Any:
        if "input[type=password]" in expression:
            return self._has_password
        # 非指纹 JS：走真正的 extract_login_form 会失败，测试只驱动 LoginWatcher
        # 的门卫/去重逻辑，因此把这里视为提取失败路径。
        return None

    def set_login(self, info: LoginFormInfo, has_password: bool = True) -> None:
        self._info = info
        self._has_password = has_password


def _record() -> dict[str, list]:
    return {"forms": []}


async def _make_watcher(
    monkeypatch,
    page: _FakePage,
    record: dict[str, list],
    info: LoginFormInfo | None = None,
) -> LoginWatcher:
    async def on_detected(form: dict[str, Any]) -> None:
        record["forms"].append(form)

    import browser.login_form as login_form_mod

    async def _fake_extract(p):
        p.extract_calls += 1
        return info if info is not None else None

    monkeypatch.setattr(login_form_mod, "extract_login_form", _fake_extract)
    w = LoginWatcher(page=page, on_detected=on_detected)
    await w.start()
    return w


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    async def wait():
        while not predicate():
            await asyncio.sleep(0.01)
    await asyncio.wait_for(wait(), timeout=timeout)


@pytest.mark.asyncio
async def test_initial_detection_reports_login_form(monkeypatch):
    """启动即检测：页面已含登录表单时，start() 后立即回调 on_detected。"""
    page = _FakePage(url="https://example.com/login", title="Sign in")
    page.set_login(_info())
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info())
    await _wait_for(lambda: len(record["forms"]) >= 1)
    assert record["forms"][0]["is_login_page"] is True
    assert record["forms"][0]["url"] == "https://example.com/login"
    await w.stop()


@pytest.mark.asyncio
async def test_incremental_detection_reports_once_per_signature(monkeypatch):
    """DOM 突变驱动：表单稳定后重复突变只上报一次（签名去重）。"""
    page = _FakePage(url="https://example.com", title="Home")
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info())
    # 弹窗延迟出现
    page.set_login(_info())
    page._exposed["__scriptordb_domChanged"]()
    await _wait_for(lambda: len(record["forms"]) >= 1)
    await asyncio.sleep(0.2)  # 窗口外再突变：签名未变 → 不重复报
    page._exposed["__scriptordb_domChanged"]()
    await asyncio.sleep(0.3)
    assert len(record["forms"]) == 1
    await w.stop()


@pytest.mark.asyncio
async def test_signature_change_reports_again(monkeypatch):
    """签名变化（表单被替换/重登）再次上报。"""
    page = _FakePage(url="https://example.com/login", title="Sign in")
    page.set_login(_info())
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info())
    await _wait_for(lambda: len(record["forms"]) >= 1)
    # 换一个密码字段选择器的表单：签名不同 → 重新上报
    other = LoginFormInfo(
        url="https://example.com/login",
        is_login_page=True,
        fields=[LoginField(role="password", selector="#newpass")],
    )
    page.set_login(other)
    import browser.login_form as login_form_mod

    async def _fake_extract_new(p):
        return other

    monkeypatch.setattr(login_form_mod, "extract_login_form", _fake_extract_new)
    page._exposed["__scriptordb_domChanged"]()
    await _wait_for(lambda: len(record["forms"]) >= 2)
    assert len(record["forms"]) == 2
    await w.stop()


@pytest.mark.asyncio
async def test_non_login_page_no_report(monkeypatch):
    """无密码框且标题无登录关键词：突变不触发上报。"""
    page = _FakePage(url="https://example.com/dashboard", title="Dashboard")
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info())
    page._exposed["__scriptordb_domChanged"]()
    await asyncio.sleep(0.5)
    assert record["forms"] == []
    await w.stop()


@pytest.mark.asyncio
async def test_stop_removes_expose_and_tasks(monkeypatch):
    """stop() 移除页面函数、取消常驻任务：不再上报。"""
    page = _FakePage(url="https://example.com/login", title="Sign in")
    page.set_login(_info())
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info())
    await _wait_for(lambda: len(record["forms"]) >= 1)
    await w.stop()
    assert "__scriptordb_domChanged" in page._removed
    assert not w.started
    assert w._running_task is None
    assert len(record["forms"]) == 1  # stop 后不再增长


def test_login_form_detected_event_shape():
    """login_form_detected 事件：类型/字段与前端契约一致。"""
    ev = login_form_detected_event(
        run_id="run_1",
        login_form={"url": "https://example.com/login",
                    "is_login_page": True, "fields": [], "submit": None},
    )
    assert ev["type"] == "login_form_detected"
    assert ev["run_id"] == "run_1"
    assert ev["login_form"]["is_login_page"] is True
    assert "timestamp" in ev


def test_human_takeover_event_includes_login_form():
    """human_takeover_request 事件携带 login_form（前端凭此渲染凭据面板）。"""
    ev = human_takeover_request_event(
        run_id="run_1",
        checkpoint_id="chk_1",
        reason="Login page detected",
        trigger="login",
        current_url="https://example.com/login",
        screenshot_available=False,
        timestamp="t",
        login_form={"url": "https://example.com/login",
                    "is_login_page": True, "fields": [], "submit": None},
    )
    assert ev["type"] == "human_takeover_request"
    assert ev["login_form"]["is_login_page"] is True

    ev2 = human_takeover_request_event(
        run_id="run_1",
        checkpoint_id="chk_1",
        reason="x",
        trigger="mfa",
        current_url="",
        screenshot_available=False,
        timestamp="t",
    )
    assert ev2["login_form"] is None
