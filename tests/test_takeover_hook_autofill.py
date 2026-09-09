from __future__ import annotations

import asyncio
from typing import Any

import pytest

from browser.autofill import AutofillDecision
from browser.takeover import HumanTakeoverManager, HumanTakeoverState
from browser.login_form import LoginFormInfo
from runtime.approval.store import get_takeover_checkpoint_store
from runtime.runner.takeover_hook import (
    AfterToolContext,
    BrowserTakeoverHook,
    RunPauseState,
)
from schemas.login_flow import LoginFlowStatus


class _FakeTakeoverMgr:
    """可注入的假浏览器 manager：hook 只用到 page/get_state/detect_takeover/takeover。"""

    def __init__(self, page, url: str = "https://example.com/login"):
        self._page = page
        self.url = url
        self.takeover = HumanTakeoverManager()
        self._detect_calls = 0

    def page(self):
        return self._page

    async def get_state(self) -> dict:
        return {"url": self.url, "actions": [], "screenshot_available": False}

    async def detect_takeover(self) -> bool:
        self._detect_calls += 1
        return False


class _FakePage:
    url = "https://example.com/login"

    def __init__(self):
        self._fills = []

    async def title(self) -> str:
        return "Login"

    async def evaluate(self, expression: str) -> Any:
        # 密码框指纹：默认登录页含密码框
        return "input[type=password]" in expression

    def locator(self, selector: str):
        return _FakeLocator(self, selector)


class _FakeLocator:
    def __init__(self, page, selector):
        self._page = page
        self.selector = selector

    async def count(self) -> int:
        return 1

    async def input_value(self) -> str:
        return ""

    async def fill(self, value: str) -> None:
        self._page._fills.append((self.selector, value))


def _info() -> LoginFormInfo:
    return LoginFormInfo(
        url="https://example.com/login",
        is_login_page=True,
        fields=[],
    )


def _flow_status(**kw) -> LoginFlowStatus:
    base: dict[str, object] = dict(
        site="example.com",
        login_form_detected=True,
        configured=True,
        username_filled=True,
        password_filled=True,
        extra_required=False,
        extra_filled=False,
        needs_otp=False,
        manual_otp_guided=False,
        fill_ok=True,
        fill_error="",
    )
    base.update(kw)
    return LoginFlowStatus(**base)


def _ctx(queue, pause: RunPauseState | None = None) -> AfterToolContext:
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


async def _await_ok(value):
    return value


async def _await_result(status, decision):
    from browser.autofill import AutofillResult

    return AutofillResult(status=status, decision=decision)


async def _wait_until(predicate, timeout: float = 2.0):
    async def wait():
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=timeout)


class TestHookAutofillOrchestration:
    async def test_non_browser_tool_skipped(self):
        """非 browser_* 工具：hook 直接返回，不触碰任何检测。"""
        queue: asyncio.Queue[dict] = asyncio.Queue()
        hook = BrowserTakeoverHook()
        ctx = _ctx(queue)
        ctx.tool_name = "query_database"
        await hook.after_tool_result(ctx)
        assert queue.empty()

    async def test_login_page_fill_ok_no_otp_resets_takeover(self, monkeypatch):
        """已配置、填完且无 otp：推 login_flow_status{fill_ok} + reset 掉误触发接管。"""
        page = _FakePage()
        info = _info()
        status = _flow_status(fill_ok=True)
        decision = AutofillDecision(kind="reset")
        # 先制造一个 login 页误触发的 DETECTED 状态
        mgr = _FakeTakeoverMgr(page)
        import browser.autofill as autofill_mod
        import browser.login_form as login_form_mod

        monkeypatch.setattr("browser.get_manager", lambda: mgr)
        monkeypatch.setattr(
            login_form_mod, "extract_login_form", lambda p: _await_ok(info)
        )
        monkeypatch.setattr(
            autofill_mod, "try_autofill",
            lambda p, i, ws: _await_result(status, decision),
        )
        mgr.takeover.request_takeover("Login page detected", "login", url=page.url)
        assert mgr.takeover.state == HumanTakeoverState.DETECTED

        queue: asyncio.Queue[dict] = asyncio.Queue()
        hook = BrowserTakeoverHook()
        await hook.after_tool_result(_ctx(queue))

        # reset：回到 RUNNING，不挂起、不存 checkpoint
        assert mgr.takeover.state == HumanTakeoverState.RUNNING
        assert mgr.takeover.reason == ""
        events: list[dict] = []
        while not queue.empty():
            events.append(queue.get_nowait())
        types = [e.get("type") for e in events]
        assert "login_flow_status" in types
        assert "human_takeover_request" not in types
        status_ev = next(e for e in events if e.get("type") == "login_flow_status")
        assert status_ev["fill_ok"] is True

    async def test_manual_otp_pauses_with_mfa_copy(self, monkeypatch):
        """otp 场景：决策 kind=pause + override mfa 文案（经 retrigger）；挂起进 WAITING_HUMAN。"""
        page = _FakePage()
        info = _info()
        status = _flow_status(
            needs_otp=True, manual_otp_guided=True,
        )
        decision = AutofillDecision(
            kind="pause",
            override_reason=True,
            reason="Credentials were filled. Enter the verification code in the Chrome window, then press Finish.",
            trigger="mfa",
        )
        mgr = _FakeTakeoverMgr(page)
        import browser.autofill as autofill_mod
        import browser.login_form as login_form_mod

        monkeypatch.setattr("browser.get_manager", lambda: mgr)
        monkeypatch.setattr(
            login_form_mod, "extract_login_form", lambda p: _await_ok(info)
        )
        monkeypatch.setattr(
            autofill_mod, "try_autofill",
            lambda p, i, ws: _await_result(status, decision),
        )
        # 模拟 detect_human_needed 已先触发 mfa（DETECTED 状态）
        mgr.takeover.request_takeover("MFA input detected", "mfa", url=page.url)

        pause = RunPauseState()
        queue: asyncio.Queue[dict] = asyncio.Queue()
        hook = BrowserTakeoverHook()
        ctx = _ctx(queue, pause)
        task = asyncio.create_task(hook.after_tool_result(ctx))
        # hook 挂起在内部 resume_event.wait()：轮询 takeover.state 直到 WAITING_HUMAN
        await _wait_until(lambda: mgr.takeover.state == HumanTakeoverState.WAITING_HUMAN)
        assert mgr.takeover.trigger == "mfa"
        assert "verification code" in mgr.takeover.reason

        # checkpoint 已存 + human_takeover_request 事件已推
        store = get_takeover_checkpoint_store()
        cp = store.get("sess_1")
        assert cp is not None
        assert cp.trigger == "mfa"

        # 恢复：唤醒 run
        pause.resume_event.set()
        await asyncio.wait_for(task, timeout=1.0)

        events: list[dict] = []
        while not queue.empty():
            events.append(queue.get_nowait())
        types = [e.get("type") for e in events]
        assert "login_flow_status" in types
        assert "human_takeover_request" in types
        store.remove("sess_1")

    async def test_unconfigured_login_pushes_status_then_pauses(self, monkeypatch):
        """未配置站点：推 login_flow_status{configured:false} 后仍走接管（默认文案）。"""
        page = _FakePage()
        info = _info()
        status = _flow_status(configured=False, fill_ok=False)
        decision = AutofillDecision(kind="pause", override_reason=False)
        mgr = _FakeTakeoverMgr(page)
        import browser.autofill as autofill_mod
        import browser.login_form as login_form_mod

        monkeypatch.setattr("browser.get_manager", lambda: mgr)
        monkeypatch.setattr(
            login_form_mod, "extract_login_form", lambda p: _await_ok(info)
        )
        monkeypatch.setattr(
            autofill_mod, "try_autofill",
            lambda p, i, ws: _await_result(status, decision),
        )
        # detect_takeover 触发 login 接管（决策未覆盖）
        mgr.takeover.request_takeover("Login page detected", "login", url=page.url)

        pause = RunPauseState()
        queue: asyncio.Queue[dict] = asyncio.Queue()
        hook = BrowserTakeoverHook()
        ctx = _ctx(queue, pause)
        task = asyncio.create_task(hook.after_tool_result(ctx))
        await _wait_until(lambda: mgr.takeover.state == HumanTakeoverState.WAITING_HUMAN)
        # 默认文案保留（未被决策覆盖）
        assert mgr.takeover.trigger == "login"

        pause.resume_event.set()
        await asyncio.wait_for(task, timeout=1.0)
        events: list[dict] = []
        while not queue.empty():
            events.append(queue.get_nowait())
        types = [e.get("type") for e in events]
        assert "login_flow_status" in types
        assert "human_takeover_request" in types
        store = get_takeover_checkpoint_store()
        store.remove("sess_1")

    async def test_non_login_page_no_autofill_status(self, monkeypatch):
        """非登录页（extract 返回 None）：不推 login_flow_status、不 autofill。"""
        page = _FakePage()
        mgr = _FakeTakeoverMgr(page)
        import browser.autofill as autofill_mod
        import browser.login_form as login_form_mod

        monkeypatch.setattr("browser.get_manager", lambda: mgr)
        monkeypatch.setattr(
            login_form_mod, "extract_login_form", lambda p: _await_ok(None)
        )
        autofill_called = False

        async def _no_autofill(p, i, ws):
            nonlocal autofill_called
            autofill_called = True
            return None

        monkeypatch.setattr(autofill_mod, "try_autofill", _no_autofill)
        queue: asyncio.Queue[dict] = asyncio.Queue()
        hook = BrowserTakeoverHook()
        await hook.after_tool_result(_ctx(queue))
        assert autofill_called is False
        events: list[dict] = []
        while not queue.empty():
            events.append(queue.get_nowait())
        assert all(e.get("type") != "login_flow_status" for e in events)

    async def test_non_login_page_cached_skips_repeat_extract(self, monkeypatch):
        """非登录页：同 URL+标题+密码框指纹的连续 tool 结果只提取一次。"""
        page = _FakePage()
        mgr = _FakeTakeoverMgr(page)
        import browser.autofill as autofill_mod
        import browser.login_form as login_form_mod

        monkeypatch.setattr("browser.get_manager", lambda: mgr)
        extract_calls = {"n": 0}
        async def _extract(p):
            extract_calls["n"] += 1
            return None  # 非登录页

        monkeypatch.setattr(login_form_mod, "extract_login_form", _extract)
        monkeypatch.setattr(autofill_mod, "try_autofill",
                            lambda p, i, ws: _await_result(
                                _flow_status(configured=False), AutofillDecision(kind="pause")
                            ))
        queue: asyncio.Queue[dict] = asyncio.Queue()
        hook = BrowserTakeoverHook()
        await hook.after_tool_result(_ctx(queue))
        # 指纹命中：第二次调用不再 extract
        await hook.after_tool_result(_ctx(queue))
        assert extract_calls["n"] == 1
        events: list[dict] = []
        while not queue.empty():
            events.append(queue.get_nowait())
        assert all(e.get("type") != "login_flow_status" for e in events)

    async def test_login_page_signature_cache_skips_repeat_autofill(self, monkeypatch):
        """登录页：同 URL+同字段签名的连续 tool 结果只 autofill 一次、不重推事件。"""
        page = _FakePage()
        info = _info()
        mgr = _FakeTakeoverMgr(page)
        import browser.autofill as autofill_mod
        import browser.login_form as login_form_mod

        monkeypatch.setattr("browser.get_manager", lambda: mgr)
        monkeypatch.setattr(
            login_form_mod, "extract_login_form", lambda p: _await_ok(info)
        )
        autofill_calls = {"n": 0}
        async def _autofill(p, i, ws):
            autofill_calls["n"] += 1
            return await _await_result(
                _flow_status(fill_ok=True), AutofillDecision(kind="reset")
            )

        monkeypatch.setattr(autofill_mod, "try_autofill", _autofill)
        queue: asyncio.Queue[dict] = asyncio.Queue()
        hook = BrowserTakeoverHook()
        await hook.after_tool_result(_ctx(queue))
        # 同 URL 且 extract 返回同签名：第二次 skip_autofill（不再调 try_autofill）
        await hook.after_tool_result(_ctx(queue))
        assert autofill_calls["n"] == 1


class TestAutofillSystemHintInjection:
    """autofill 完成（configured + fill_ok）后向模型注入系统代填提示，同实例只一次。"""

    def _ctx_with_enqueue(self, queue, enqueued: list[str]) -> AfterToolContext:
        ctx = _ctx(queue)

        class _FakeRunCtx:
            async def enqueue(self, text: str) -> None:
                enqueued.append(text)

        ctx.ctx = _FakeRunCtx()
        return ctx

    async def test_configured_fill_ok_injects_hint_once(self, monkeypatch):
        """configured + fill_ok：注入提示；同 hook 实例第二次调用不重复注入。"""
        page = _FakePage()
        info = _info()
        status = _flow_status(fill_ok=True)
        decision = AutofillDecision(kind="reset")
        mgr = _FakeTakeoverMgr(page)
        import browser.autofill as autofill_mod
        import browser.login_form as login_form_mod

        monkeypatch.setattr("browser.get_manager", lambda: mgr)
        monkeypatch.setattr(
            login_form_mod, "extract_login_form", lambda p: _await_ok(info)
        )
        monkeypatch.setattr(
            autofill_mod, "try_autofill",
            lambda p, i, ws: _await_result(status, decision),
        )
        queue: asyncio.Queue[dict] = asyncio.Queue()
        enqueued: list[str] = []
        hook = BrowserTakeoverHook()
        await hook.after_tool_result(self._ctx_with_enqueue(queue, enqueued))
        await hook.after_tool_result(self._ctx_with_enqueue(queue, enqueued))

        assert len(enqueued) == 1
        assert "系统站点凭证已自动填充" in enqueued[0]
        assert "密码字段" in enqueued[0]


