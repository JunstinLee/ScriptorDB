"""Q1:保存凭证后 autofill 立即填充 —— LoginWatcher 填表候选与记忆重置。

场景:用户保存站点凭证前,watcher 已对同一登录表单试过一次填表(未配置、
没填成);保存动作本身不改变表单样子,若填表尝试与事件上报共用同一套
签名去重,保存后 watcher 会永远跳过、不重试。本测试验证:
- 发现登录页时触发一次「填表候选」回调(与事件上报并列,但独立去重);
- 表单未变时填表候选不重复触发(去重),事件上报也不重复;
- clear_autofill_memory()(凭证保存成功后调用)清空填表记忆 → 下一轮
  重新触发填表候选,而事件上报仍被签名去重挡住(前端不重复弹面板);
- 表单签名变化(重登/替换)时填表候选重新触发;
- 未提供填表回调时维持旧行为(只上报事件,不记填表记忆)。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from browser.login_form import LoginField, LoginFormInfo
from browser.login_watcher import LoginWatcher, clear_autofill_memory


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
    """最小 Page 接口:指纹 JS / 提取 JS / observer 安装均由测试控制。"""

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
        return None

    def set_login(self, info: LoginFormInfo, has_password: bool = True) -> None:
        self._info = info
        self._has_password = has_password


def _record() -> dict[str, list]:
    return {"forms": [], "candidates": []}


async def _make_watcher(
    monkeypatch,
    page: _FakePage,
    record: dict[str, list],
    info: LoginFormInfo | None = None,
    with_candidate: bool = False,
) -> LoginWatcher:
    async def on_detected(form: dict[str, Any]) -> None:
        record["forms"].append(form)

    async def on_candidate(form: Any) -> None:
        record["candidates"].append(form)

    import browser.login_form as login_form_mod

    async def _fake_extract(p):
        p.extract_calls += 1
        return info if info is not None else None

    monkeypatch.setattr(login_form_mod, "extract_login_form", _fake_extract)
    w = LoginWatcher(
        page=page,
        on_detected=on_detected,
        on_autofill_candidate=on_candidate if with_candidate else None,
    )
    await w.start()
    return w


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    async def wait():
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=timeout)


@pytest.mark.asyncio
async def test_candidate_fires_on_first_detection(monkeypatch):
    """发现登录页即触发一次填表候选(结构化表单对象);事件上报照旧。"""
    page = _FakePage(url="https://example.com/login", title="Sign in")
    page.set_login(_info())
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info(),
                            with_candidate=True)
    await _wait_for(lambda: len(record["candidates"]) >= 1)
    assert len(record["forms"]) >= 1
    cand = record["candidates"][0]
    assert cand.url == "https://example.com/login"
    assert cand.signature() == _info().signature()
    await w.stop()


@pytest.mark.asyncio
async def test_candidate_deduped_until_memory_cleared(monkeypatch):
    """表单未变:填表候选只触发一次;clear_autofill_memory() 后重新触发。"""
    page = _FakePage(url="https://example.com/login", title="Sign in")
    page.set_login(_info())
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info(),
                            with_candidate=True)
    await _wait_for(lambda: len(record["candidates"]) >= 1)
    await asyncio.sleep(0.2)
    assert len(record["candidates"]) == 1
    assert len(record["forms"]) == 1

    # 模拟凭证保存成功:清空填表记忆 → 候选重新触发;事件上报仍去重
    clear_autofill_memory()
    page._exposed["__scriptordb_domChanged"]()
    await _wait_for(lambda: len(record["candidates"]) >= 2)
    assert len(record["candidates"]) == 2
    assert len(record["forms"]) == 1
    await w.stop()


@pytest.mark.asyncio
async def test_candidate_retries_after_signature_change(monkeypatch):
    """表单重登/替换(签名变化):填表候选重新触发。"""
    page = _FakePage(url="https://example.com/login", title="Sign in")
    page.set_login(_info())
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info(),
                            with_candidate=True)
    await _wait_for(lambda: len(record["candidates"]) >= 1)

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
    await _wait_for(lambda: len(record["candidates"]) >= 2)
    assert len(record["candidates"]) == 2
    await w.stop()


@pytest.mark.asyncio
async def test_candidate_absent_without_callback(monkeypatch):
    """未提供填表回调:不触发候选、不记填表记忆(旧行为保持)。"""
    page = _FakePage(url="https://example.com/login", title="Sign in")
    page.set_login(_info())
    record = _record()
    w = await _make_watcher(monkeypatch, page, record, info=_info(),
                            with_candidate=False)
    await _wait_for(lambda: len(record["forms"]) >= 1)
    await asyncio.sleep(0.2)
    assert record["candidates"] == []
    assert w._autofill_sig is None
    await w.stop()


@pytest.mark.asyncio
async def test_clear_memory_is_noop_without_active_watchers():
    """无活跃 watcher(会话结束/浏览器未开):清记忆为空操作,不报错。"""
    clear_autofill_memory()  # 不抛异常即通过
