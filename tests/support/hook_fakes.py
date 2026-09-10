"""接管 hook 测试共享假件：假 manager / page / locator 与上下文构造器。"""

from __future__ import annotations

import asyncio
from typing import Any

from browser.login_form import LoginFormInfo
from browser.takeover import HumanTakeoverManager
from runtime.runner.takeover_hook import AfterToolContext, RunPauseState
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
    base: dict[str, Any] = dict(
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

