"""SSE 断连丢弃挂起 run 时终态收敛的专项测试（阶段三兜底）。

核心契约：
- 断连仍取消挂起的 run（run 生存期不变），但取消前把暂停态收敛为终态：
  接管 checkpoint 落盘为 cancelled run、内存 store 清空、takeover 状态机复位。
- 审批挂起的 pending 在断连时被清空并归档为 cancelled run。
- 恢复/审批端点在无活动 run 时返回可操作的 404 文案，而非裸 404。
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ToolCallPart,
    ToolReturnPart,
)

from browser import get_manager
from browser.takeover import HumanTakeoverState
from config.app_config import AppConfig
from runtime.approval.orchestrator import ApprovalOrchestrator
from runtime.approval.store import (
    PendingApproval,
    get_pending_store,
    get_takeover_checkpoint_store,
)
from runtime.session_file_store import FileSessionStore
from schemas import ApprovalSubmitRequest

from api.routes import approve as approve_route
from api.routes import browser_interact
from api.routes.browser_interact import (
    TakeoverCancelRequest,
    TakeoverCompleteRequest,
    complete_human_takeover,
)
from api.routes.chat import _active_orchestrators, _stream_orchestrator_events


class FakeAgent:
    """browser 工具一把 + 无限挂起：模拟处在暂停态（接管/审批）中的 run。"""

    def __init__(self) -> None:
        self.cancelled = False

    async def run(self, prompt, **kwargs):
        handler = kwargs["event_stream_handler"]

        async def events():
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
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                self.cancelled = True
                raise

        try:
            await handler(SimpleNamespace(), events())
        except asyncio.CancelledError:
            # 模拟 pydantic-ai：外部取消（页面断开）传播到 run
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


@pytest.fixture
def store(tmp_path):
    return FileSessionStore(tmp_path / "sessions")


def _patch_store(monkeypatch, store):
    monkeypatch.setattr("runtime.sessions.get_session_store", lambda: store)
    monkeypatch.setattr("services.chat_service.get_session_store", lambda: store)
    monkeypatch.setattr(
        "runtime.approval.orchestrator.get_session_store", lambda: store
    )


async def _await_true(flag, timeout: float = 5.0):
    async def wait():
        while not flag():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=timeout)


async def _start_stream(orchestrator, sid) -> asyncio.Task:
    """启动 chat SSE 流并返回其消费 task（断连 = 取消该 task）。"""
    _active_orchestrators[sid] = orchestrator
    response = await _stream_orchestrator_events(orchestrator, "hi", [], sid)
    chunks: list[Any] = []

    async def consume():
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    return asyncio.create_task(consume())


async def _disconnect(consumer: asyncio.Task) -> None:
    """模拟客户端断开：取消 SSE 消费 task（走 generate() 的取消分支）。"""
    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


async def test_takeover_pause_disconnect_persists_cancelled_run(monkeypatch, store):
    """接管挂起中断连：checkpoint 归档为 cancelled run，takeover 状态机复位。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    agent = FakeAgent()
    orchestrator = ApprovalOrchestrator(sid, AppConfig(), agent=agent)
    consumer = await _start_stream(orchestrator, sid)

    await _await_true(lambda: mgr.takeover.state == HumanTakeoverState.WAITING_HUMAN)
    assert get_takeover_checkpoint_store().get(sid) is not None
    run_id = orchestrator.run_id

    await _disconnect(consumer)

    assert agent.cancelled
    assert get_takeover_checkpoint_store().get(sid) is None
    assert mgr.takeover.state == HumanTakeoverState.RUNNING

    session = store.get(sid)
    assert session is not None
    assert any(
        r.run_id == run_id and r.status == "cancelled" for r in session.runs
    )


async def test_approval_pause_disconnect_clears_pending(monkeypatch, store):
    """审批挂起中断连：该 session 的 pending 清空并归档为 cancelled run。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id

    agent = FakeAgent()
    orchestrator = ApprovalOrchestrator(sid, AppConfig(), agent=agent)
    consumer = await _start_stream(orchestrator, sid)
    await _await_true(lambda: orchestrator.run_id != "")
    run_id = orchestrator.run_id

    pending_store = get_pending_store()
    pending_store.add(
        "req_abandon",
        PendingApproval(
            request_id="req_abandon",
            session_id=sid,
            run_id=run_id,
            message_history=[],
            deferred_calls=[],
        ),
    )
    try:
        await _disconnect(consumer)

        assert pending_store.get("req_abandon") is None
        session = store.get(sid)
        assert session is not None
        assert any(
            r.run_id == run_id and r.status == "cancelled" for r in session.runs
        )
    finally:
        pending_store.pop("req_abandon")


async def test_recovery_endpoints_report_abandoned_run(monkeypatch):
    """无活动 run 时恢复/审批/取消端点返回可操作的 404 文案。"""
    monkeypatch.setattr(browser_interact, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(browser_interact, "get_config", lambda: AppConfig())
    monkeypatch.setattr(browser_interact, "get_orchestrator", lambda sid: None)
    monkeypatch.setattr(approve_route, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(approve_route, "get_orchestrator", lambda sid: None)

    with pytest.raises(HTTPException) as exc:
        await complete_human_takeover(
            TakeoverCompleteRequest(session_id="sess_1", result="x")
        )
    assert exc.value.status_code == 404
    assert "event stream dropped" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        await browser_interact.cancel_takeover(
            TakeoverCancelRequest(session_id="sess_1")
        )
    assert exc.value.status_code == 404
    assert "event stream dropped" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        await approve_route.approve(
            "sess_1",
            ApprovalSubmitRequest(request_id="req_1", approved_map={}),
        )
    assert exc.value.status_code == 404
    assert "event stream dropped" in exc.value.detail
