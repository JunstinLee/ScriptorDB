"""人工接管 = run 内部暂停点（而非 run 结束 + 重启）的专项测试。

核心契约：
- 检测到接管后 agent run 挂起在 resume_event 上，不结束、不取消。
- /takeover/complete 通过 resume_event.set() 唤醒同一个 run（无第二次
  agent.run()），恢复后原执行栈继续到 run_end。
- 取消/超时唤醒后走 takeover_cancelled 终态（status=cancelled）。
- 恢复时把"用户完成了人工操作"经 RunContext.enqueue 注入对话。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelRequest,
    ToolCallPart,
    ToolReturnPart,
)

from browser import get_manager
from browser.takeover import HumanTakeoverState
from config.app_config import AppConfig
from runtime.agent_runner import run_agent_stream
from runtime.approval_orchestrator import ApprovalOrchestrator
from runtime.approval_policy import get_takeover_checkpoint_store
from runtime.runner.takeover_hook import RunPauseState, TakeoverCancelledError
from api.routes.chat import (
    _active_orchestrators,
    _stream_orchestrator_events,
    get_orchestrator,
)
from runtime.session_file_store import FileSessionStore


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

        try:
            await event_stream_handler(run_ctx, events())
        except asyncio.CancelledError:
            # 模拟 pydantic-ai：外部取消（页面断开/显式关闭）传播到 run
            self.cancelled = True
            raise

        return SimpleNamespace(
            output="ok",
            new_messages=lambda: [],
            all_messages=lambda: [],
        )


@pytest.fixture(autouse=True)
def _reset_takeover():
    mgr = get_manager()
    mgr.takeover.reset()
    yield
    mgr.takeover.reset()


def _patch_store(monkeypatch, store):
    monkeypatch.setattr("runtime.sessions.get_session_store", lambda: store)
    monkeypatch.setattr("services.chat_service.get_session_store", lambda: store)
    monkeypatch.setattr(
        "approval_part.orchestrator.get_session_store", lambda: store
    )


@pytest.fixture
def store(tmp_path):
    return FileSessionStore(tmp_path / "sessions")


async def _collect_until(gen, target_type: str, timeout: float = 5.0):
    seen = []
    done = False

    async def consume():
        nonlocal done
        async for ev in gen:
            seen.append(ev)
            if ev.get("type") == target_type:
                done = True
                return

    await asyncio.wait_for(asyncio.create_task(consume()), timeout=timeout)
    return seen, done


async def _await_true(flag, timeout: float = 5.0):
    async def wait():
        while not flag():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=timeout)


async def _noop_cb(event):
    return None


async def _start_and_wait_paused(orchestrator, mgr):
    run_task = asyncio.create_task(orchestrator.start_run("hi", [], _noop_cb))
    await _await_true(lambda: mgr.takeover.state == HumanTakeoverState.WAITING_HUMAN)
    return run_task


async def _finish_run(run_task, agent, timeout: float = 5.0):
    agent.release = True
    return await asyncio.wait_for(run_task, timeout=timeout)


# ---------- 挂起 / 恢复 ----------


async def test_takeover_pause_holds_run_not_cancelled():
    """接管是 run 内部暂停点：agent task 挂起而非取消，等待 resume 事件。"""
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    agent = FakeAgent(mode="block")
    pause = RunPauseState()
    gen = run_agent_stream("hi", [], AppConfig(), agent=agent, pause=pause)

    seen, paused = await _collect_until(gen, "human_takeover_request")
    assert paused
    assert any(ev["type"] == "tool_result" for ev in seen)

    # 挂起期间：agent task 存活（未被取消）；探测事件会取消生成器，
    # 因此用时间流逝 + 恢复来验证。
    await asyncio.sleep(0.3)
    assert not agent.cancelled

    # 恢复：唤醒同一 run，agent 仍不被取消
    pause.resume_event.set()
    await asyncio.sleep(0.2)
    assert not agent.cancelled

    await gen.aclose()
    assert agent.cancelled  # 显式关闭才取消内部 task


async def test_takeover_resume_wakes_same_run():
    """resume_event.set() 唤醒同一 run：原执行栈继续到 run_end。"""
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    agent = FakeAgent(mode="block")
    pause = RunPauseState()
    gen = run_agent_stream("hi", [], AppConfig(), agent=agent, pause=pause)

    seen, paused = await _collect_until(gen, "human_takeover_request")
    assert paused

    # 用户完成接管：记录结果并 resume 唤醒 hook
    mgr.takeover.complete("完成登录")
    agent.release = True
    pause.resume_event.set()

    events = list(seen)
    async for ev in gen:
        events.append(ev)

    assert any(ev["type"] == "run_end" for ev in events)
    assert not agent.cancelled
    assert "".join(str(c) for c in agent.ctx.enqueued) == "用户完成了人工操作: 完成登录"


# ---------- orchestrator 层 ----------


async def test_resume_takeover_validates_run_id(monkeypatch, store):
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = await _start_and_wait_paused(orchestrator, mgr)

    assert orchestrator.run_id

    wrong = orchestrator.resume_takeover("wrong-run-id", "done")
    assert wrong == {"ok": False, "error": "run_mismatch"}

    right = orchestrator.resume_takeover(orchestrator.run_id, "done")
    assert right["ok"] is True
    assert right["status"] == "resumed"
    assert right["run_id"] == orchestrator.run_id

    # 唤醒后原 run 继续执行到完成
    summary = await _finish_run(run_task, agent)
    assert summary["status"] == "completed"
    assert agent.ctx.enqueued
    assert agent.last_prompt == "hi"  # 同一 run，没有第二次 agent.run()


async def test_resume_injects_takeover_result_message(monkeypatch, store):
    """恢复不是重启：同一 run 内把用户操作结果经 enqueue 注入对话。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = await _start_and_wait_paused(orchestrator, mgr)
    assert get_takeover_checkpoint_store().get(sid) is not None

    ok = orchestrator.resume_takeover(orchestrator.run_id, "完成登录")
    assert ok["ok"] is True
    summary = await _finish_run(run_task, agent)
    assert summary["status"] == "completed"

    enqueued = "".join(str(c) for c in agent.ctx.enqueued)
    assert "用户完成了人工操作" in enqueued
    assert "完成登录" in enqueued


# ---------- checkpoint 仍用于取消终态 ----------


async def test_checkpoint_contains_tool_call_and_result(monkeypatch, store):
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)

    seen = []
    async def _collect(ev):
        seen.append(ev)
    run_task = asyncio.create_task(orchestrator.start_run("hi", [], _collect))
    await _await_true(lambda: mgr.takeover.state == HumanTakeoverState.WAITING_HUMAN)
    assert any(ev["type"] == "human_takeover_request" for ev in seen)

    ckpt = get_takeover_checkpoint_store().get(sid)
    assert ckpt is not None
    assert ckpt.run_id == orchestrator.run_id
    assert ckpt.session_id == sid
    assert ckpt.reason == "unit test"
    assert ckpt.prompt == "hi"
    assert len(ckpt.turn_new_messages) == 1
    request = ckpt.turn_new_messages[0]
    assert isinstance(request, ModelRequest)
    assert any(isinstance(p, ToolCallPart) for p in request.parts)
    assert any(isinstance(p, ToolReturnPart) for p in request.parts)

    request_event = next(ev for ev in seen if ev["type"] == "human_takeover_request")
    assert request_event.get("checkpoint_id") == ckpt.checkpoint_id
    assert "messages" not in request_event

    # 唤醒挂起的 run 后完成
    assert orchestrator.resume_takeover(orchestrator.run_id, "done")["ok"]
    await _finish_run(run_task, agent)


# ---------- 取消 / 超时 ----------


async def test_cancel_takeover_terminates_and_persists(monkeypatch, store):
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = await _start_and_wait_paused(orchestrator, mgr)
    assert orchestrator.run_id

    result = orchestrator.cancel_takeover(orchestrator.run_id, "用户取消接管")
    assert result == {"ok": True, "status": "cancelled", "reason": "用户取消接管"}

    assert get_takeover_checkpoint_store().get(sid) is None
    assert mgr.takeover.state == HumanTakeoverState.CANCELLED

    session = store.get(sid)
    assert session is not None
    assert any(r.run_id == orchestrator.run_id and r.status == "cancelled" for r in session.runs)
    assert len(session.model_messages) == 1
    assert any(isinstance(p, ToolCallPart) for p in session.model_messages[0].parts)

    # 取消唤醒挂起的 run：走 takeover_cancelled 终态结束
    summary = await asyncio.wait_for(run_task, timeout=5.0)
    assert summary["status"] == "cancelled"

    again = orchestrator.cancel_takeover(orchestrator.run_id, "重复取消")
    assert again == {"ok": False, "error": "no_active_takeover", "status": "not_cancelled"}


async def test_cancel_takeover_run_mismatch(monkeypatch, store):
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = await _start_and_wait_paused(orchestrator, mgr)

    result = orchestrator.cancel_takeover("wrong-run-id", "取消")
    assert result == {"ok": False, "error": "run_mismatch", "status": "not_cancelled"}
    assert get_takeover_checkpoint_store().get(sid) is not None

    # 清理：mismatch 未唤醒，显式取消结束 run
    orchestrator.cancel_takeover(orchestrator.run_id, "清理")
    await asyncio.wait_for(run_task, timeout=5.0)


async def test_takeover_timeout_cancels_run(monkeypatch, store):
    """超时（TAKEOVER_TIMEOUT 无人响应）也唤醒挂起的 run 并走取消终态。"""
    import browser.takeover as takeover_mod

    monkeypatch.setattr(takeover_mod, "TAKEOVER_TIMEOUT", 0.2)
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = await _start_and_wait_paused(orchestrator, mgr)

    summary = await asyncio.wait_for(run_task, timeout=5.0)
    assert summary["status"] == "cancelled"
    # 终态处理后 takeover 被重置（_run_loop 的 takeover_cancelled 分支）
    assert mgr.takeover.state == HumanTakeoverState.RUNNING
    assert get_takeover_checkpoint_store().get(sid) is None


async def test_cancel_then_new_message_starts_new_run(monkeypatch, store):
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    run_task = await _start_and_wait_paused(orchestrator, mgr)
    run1 = orchestrator.run_id

    orchestrator.cancel_takeover(run1, "取消")
    await asyncio.wait_for(run_task, timeout=5.0)

    config2 = AppConfig()
    config2.chat_session_id = sid
    agent2 = FakeAgent(mode="complete")
    orchestrator2 = ApprovalOrchestrator(sid, config2, agent=agent2)
    summary = await orchestrator2.start_run("next message", [], _noop_cb)
    assert summary["status"] == "completed"
    assert agent2.last_prompt == "next message"


# ---------- SSE 流 ----------


async def test_chat_sse_takeover_pause_keeps_stream_open(monkeypatch, store):
    """接管期间 SSE 流保持打开；恢复后同一 run 的事件继续推送至 run_end。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    _active_orchestrators[sid] = orchestrator

    response = await _stream_orchestrator_events(orchestrator, "hi", [], sid)
    chunks: list[Any] = []

    async def consume():
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    consumer = asyncio.create_task(consume())
    await _await_true(lambda: any("human_takeover_request" in c for c in chunks))

    # 接管期间：SSE 流保持打开，run 挂起未取消，orchestrator 保留
    await asyncio.sleep(0.2)
    assert not consumer.done()
    assert not agent.cancelled
    assert get_orchestrator(sid) is not None

    # 恢复：同一 run 继续，SSE 流推送 run_end 后结束
    mgr.takeover.complete("done")
    agent.release = True
    assert orchestrator.resume_takeover(orchestrator.run_id, "done")["ok"]
    await asyncio.wait_for(consumer, timeout=5.0)

    assert not agent.cancelled
    assert any("human_takeover_request" in c for c in chunks)
    assert any("run_end" in c for c in chunks)
