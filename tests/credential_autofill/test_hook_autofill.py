"""Q1:保存凭证后 autofill 立即填充 —— hook 侧 watcher 填表候选接线。

验证 `takeover_hook._ensure_watcher` 创建的 LoginWatcher:
- 发现登录页 → 触发填表候选 → 调 try_autofill 填表 → 推 login_flow_status;
- 只填不唤醒:即使填好(configured+fill_ok),也不 set 挂起的 resume_event、
  不 complete takeover —— agent 保持挂起等用户点 Finish(既有接管语义)。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from browser.login_form import LoginFormInfo
from browser.login_watcher import LoginWatcher
from runtime.runner.takeover_hook import (
    AfterToolContext,
    BrowserTakeoverHook,
    RunPauseState,
)


class _FakePage:
    """最小 Page 接口：watcher 指纹/提取安装 + hook 无需真实浏览器。"""

    url = "https://example.com/login"

    def __init__(self):
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
        # 密码框指纹：登录页含密码框
        return "input[type=password]" in expression


def _info() -> LoginFormInfo:
    return LoginFormInfo(
        url="https://example.com/login",
        is_login_page=True,
        fields=[],
    )


async def _await_ok(value):
    return value


class _FlowStatus:
    """LoginFlowStatus 的轻量替身：hook 只读其字段推事件。"""

    def __init__(self, **kw):
        self.site = kw.get("site", "example.com")
        self.login_form_detected = kw.get("login_form_detected", True)
        self.configured = kw.get("configured", True)
        self.username_filled = kw.get("username_filled", True)
        self.password_filled = kw.get("password_filled", True)
        self.extra_required = kw.get("extra_required", False)
        self.extra_filled = kw.get("extra_filled", False)
        self.needs_otp = kw.get("needs_otp", False)
        self.manual_otp_guided = kw.get("manual_otp_guided", False)
        self.fill_ok = kw.get("fill_ok", True)
        self.fill_error = kw.get("fill_error", "")

    def model_dump(self) -> dict:
        from schemas.login_flow import LoginFlowStatus

        return LoginFlowStatus(**self.__dict__).model_dump()


class _AutofillResult:
    def __init__(self, status):
        self.status = status


def _ctx(queue, pause: RunPauseState) -> AfterToolContext:
    return AfterToolContext(
        queue=queue,
        tool_name="browser_navigate",
        success=True,
        session_id="sess_1",
        run_id="run_1",
        checkpoint_id="chk_1",
        prompt="do it",
        message_history=[],
        tool_parts=[],
        tool_invocations=[],
        final_output="",
        pause=pause,
    )


async def _wait_for(predicate, timeout: float = 3.0) -> None:
    async def wait():
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=timeout)


async def _start_hook_watcher(monkeypatch, ctx, page, status) -> BrowserTakeoverHook:
    """monkeypatch extract/autofill 后经 hook._ensure_watcher 起真 watcher。"""
    import browser.login_form as login_form_mod
    import browser.autofill as autofill_mod

    monkeypatch.setattr(
        login_form_mod, "extract_login_form", lambda p: _await_ok(_info())
    )

    async def _fake_autofill(p, info, ws):
        return _AutofillResult(status)

    monkeypatch.setattr(autofill_mod, "try_autofill", _fake_autofill)
    hook = BrowserTakeoverHook()
    await hook._ensure_watcher(ctx, page)
    return hook


@pytest.mark.asyncio
async def test_watcher_candidate_fill_pushes_status_only(monkeypatch):
    """watcher 触发填表:调 try_autofill 并推 login_flow_status;不唤醒挂起的 run。"""
    pause = RunPauseState()
    queue: asyncio.Queue[dict] = asyncio.Queue()
    ctx = _ctx(queue, pause)

    class _Deps:
        workspace_id = "ws_1"

    class _FakeRunCtx:
        deps = _Deps()

        async def enqueue(self, *a):
            pass

    ctx.ctx = _FakeRunCtx()

    page = _FakePage()
    status = _FlowStatus(configured=True, fill_ok=True)
    hook = await _start_hook_watcher(monkeypatch, ctx, page, status)

    # watcher 初始检测触发填表候选 → 状态事件入队
    await _wait_for(lambda: not queue.empty())
    events: list[dict] = []
    while not queue.empty():
        events.append(queue.get_nowait())
    types = [e.get("type") for e in events]
    assert "login_flow_status" in types
    status_ev = next(e for e in events if e.get("type") == "login_flow_status")
    assert status_ev["fill_ok"] is True

    # 只填不唤醒:resume_event 未 set
    assert not pause.resume_event.is_set()

    await hook.shutdown(ctx.run_id)


@pytest.mark.asyncio
async def test_watcher_candidate_unconfigured_pushes_status(monkeypatch):
    """未配置:watcher 触发填表也推状态(configured=false),不唤醒。"""
    pause = RunPauseState()
    queue: asyncio.Queue[dict] = asyncio.Queue()
    ctx = _ctx(queue, pause)
    ctx.ctx = None  # 无 deps → workspace_id 空 → 按未配置处理

    page = _FakePage()
    status = _FlowStatus(configured=False, fill_ok=False)
    hook = await _start_hook_watcher(monkeypatch, ctx, page, status)

    await _wait_for(lambda: not queue.empty())
    events: list[dict] = []
    while not queue.empty():
        events.append(queue.get_nowait())
    types = [e.get("type") for e in events]
    assert "login_flow_status" in types
    status_ev = next(e for e in events if e.get("type") == "login_flow_status")
    assert status_ev["configured"] is False
    assert not pause.resume_event.is_set()

    await hook.shutdown(ctx.run_id)
