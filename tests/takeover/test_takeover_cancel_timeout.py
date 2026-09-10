"""接管取消 / 超时：唤醒挂起的 run 并收敛到 cancelled 终态。"""

from __future__ import annotations

import asyncio

import pytest
from pydantic_ai.messages import ModelRequest, ToolCallPart, ToolReturnPart

from browser import get_manager
from browser.takeover import HumanTakeoverState
from config.app_config import AppConfig
from runtime.approval.orchestrator import ApprovalOrchestrator
from runtime.approval.store import get_takeover_checkpoint_store
from tests.support.ctx import await_true as _await_true, noop_cb as _noop_cb
from tests.support.stubs import patch_store as _patch_store
from tests.support.takeover import (
    FakeAgent,
    finish_run as _finish_run,
    start_and_wait_paused as _start_and_wait_paused,
)


@pytest.fixture(autouse=True)
def _reset_takeover():
    mgr = get_manager()
    mgr.takeover.reset()
    yield
    mgr.takeover.reset()


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


