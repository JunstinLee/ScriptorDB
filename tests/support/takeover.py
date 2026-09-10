"""接管/审批测试共享脚手架：假 agent、假 RunContext、槽位启动与唤醒。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelRequest,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from browser.takeover import HumanTakeoverState
from config.app_config import AppConfig
from runtime.approval.event_bus import RunEventBus
from runtime.approval.orchestrator import ApprovalOrchestrator
from runtime.approval.run_owner import execute_run
from runtime.approval.run_registry import ActiveRun, get_run_registry
from runtime.runner.takeover_hook import TakeoverCancelledError
from tests.support.ctx import await_true, noop_cb


def start_slot(sid: str, orchestrator: ApprovalOrchestrator) -> ActiveRun:
    """按 chat() 的方式注册槽位并启动 owner task。"""
    slot = ActiveRun(session_id=sid, orchestrator=orchestrator, bus=RunEventBus())
    get_run_registry().register(slot)
    slot.task = asyncio.create_task(
        execute_run(slot=slot, prompt="hi", message_history=[])
    )
    return slot


def start_run(sid: str, agent: Any) -> ActiveRun:
    """用给定假 agent 建 orchestrator 并按 chat() 的方式注册、启动 owner task。"""
    orchestrator = ApprovalOrchestrator(sid, AppConfig(), agent=agent)
    return start_slot(sid, orchestrator)


class FakeRunContext:
    """最小 RunContext 替身：支持 cancel()/enqueue()，供 hook 的恢复/取消路径。"""

    def __init__(self):
        self.cancelled = False
        self.enqueued: list = []

    def cancel(self):
        self.cancelled = True

    async def enqueue(self, *content):
        self.enqueued.extend(content)


class FakeAgent:
    """browser tool 一把 + block 挂起：tool result 后等待取消/释放信号。"""

    def __init__(self, mode: str = "block", delay_before_tool: float = 0):
        self.mode = mode
        self.delay_before_tool = delay_before_tool
        self.cancelled = False
        self.release = False  # block 模式：置位后正常结束（模拟接管恢复）
        self.events_produced = 0
        self.last_history: list = []
        self.last_prompt: str = ""
        self.ctx = FakeRunContext()

    async def run(self, prompt, **kwargs):
        handler = kwargs.get("event_stream_handler")
        assert handler is not None
        event_stream_handler = handler
        self.last_history = list(kwargs.get("message_history") or [])
        self.last_prompt = prompt
        run_ctx = self.ctx

        async def events():
            if self.delay_before_tool:
                try:
                    await asyncio.sleep(self.delay_before_tool)
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise
            yield FunctionToolCallEvent(
                part=ToolCallPart(
                    tool_name="browser_fake", args="{}", tool_call_id="call_1"
                )
            )
            yield FunctionToolResultEvent(
                part=ToolReturnPart(
                    tool_name="browser_fake", content="done", tool_call_id="call_1"
                )
            )
            if self.mode == "block":
                try:
                    while not run_ctx.cancelled and not self.release:
                        await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise
                if run_ctx.cancelled:
                    # 模拟 pydantic-ai 收到 ctx.cancel() 后终止 run
                    raise TakeoverCancelledError("test")
            elif self.mode == "loop":
                while True:
                    await asyncio.sleep(0.01)
                    self.events_produced += 1
                    yield FunctionToolCallEvent(
                        part=ToolCallPart(
                            tool_name="browser_loop",
                            args="{}",
                            tool_call_id=f"call_{self.events_produced}",
                        )
                    )

        try:
            await event_stream_handler(run_ctx, events())
        except asyncio.CancelledError:
            # 模拟 pydantic-ai：外部取消（页面断开/显式关闭）传播到 run
            self.cancelled = True
            raise

        if self.mode == "deferred":
            return SimpleNamespace(
                output=DeferredToolRequests(
                    calls=[ToolCallPart(tool_name="get_schema", args={})]
                ),
                new_messages=lambda: [
                    ModelRequest(parts=[UserPromptPart(content="continue")])
                ],
                all_messages=lambda: [],
            )
        return SimpleNamespace(
            output="ok",
            new_messages=lambda: [],
            all_messages=lambda: [],
        )



async def start_and_wait_paused(orchestrator: Any, mgr: Any):
    run_task = asyncio.create_task(orchestrator.start_run("hi", [], noop_cb))
    await await_true(lambda: mgr.takeover.state == HumanTakeoverState.WAITING_HUMAN)
    return run_task


async def finish_run(run_task: Any, agent: Any, timeout: float = 5.0) -> Any:
    agent.release = True
    return await asyncio.wait_for(run_task, timeout=timeout)
