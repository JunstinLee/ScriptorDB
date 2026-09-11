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


from tests.support.hook_fakes import (
    _FakePage,
    _FakeTakeoverMgr,
    _await_ok,
    _await_result,
    _ctx,
    _flow_status,
    _info,
    _wait_until,
)


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


