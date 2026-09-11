"""autofill 完成后向模型注入系统代填提示（同实例只一次）。"""

from __future__ import annotations

import asyncio

from browser.autofill import AutofillDecision
from runtime.runner.takeover_hook import AfterToolContext, BrowserTakeoverHook
from tests.support.hook_fakes import (
    _FakePage,
    _FakeTakeoverMgr,
    _await_ok,
    _await_result,
    _ctx,
    _flow_status,
    _info,
)


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


