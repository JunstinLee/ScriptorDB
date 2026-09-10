from __future__ import annotations

import asyncio
from contextlib import suppress
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from browser import get_manager
from browser.takeover import HumanTakeoverState
from config.app_config import AppConfig
from runtime.agent_runner import run_agent_stream
from runtime.approval.orchestrator import ApprovalOrchestrator
from runtime.approval.event_bus import RunEventBus
from runtime.approval.run_owner import execute_run
from runtime.approval.run_registry import ActiveRun, get_run_registry
from api.routes.browser_interact import (
    TakeoverCompleteRequest,
    complete_human_takeover,
)
from api.routes import chat as chat_route
from runtime.session_file_store import FileSessionStore


def _sse_response(bus: RunEventBus, sid: str, from_index: int = 0) -> StreamingResponse:
    return StreamingResponse(
        chat_route._stream_bus(bus, from_index, sid),
        media_type="text/event-stream",
    )


class _RegistryStub:
    """按 session 返回固定槽位（或 None）的注册表替身，供路由用例注入。"""

    def __init__(self, slot: Any | None) -> None:
        self._slot = slot

    def get(self, session_id: str):
        return self._slot

    def remove(self, session_id: str, run_id: str = ""):
        return self._slot


def _start_run(sid: str, agent: Any) -> ActiveRun:
    """按 chat() 的方式建槽位、注册、建 task（owner 不自行创建）。"""
    orchestrator = ApprovalOrchestrator(sid, AppConfig(), agent=agent)
    slot = ActiveRun(session_id=sid, orchestrator=orchestrator, bus=RunEventBus())
    get_run_registry().register(slot)
    slot.task = asyncio.create_task(
        execute_run(slot=slot, prompt="hi", message_history=[])
    )
    return slot


class FakeAgent:
    def __init__(self, mode: str = "block", delay_before_tool: float = 0):
        self.mode = mode
        self.delay_before_tool = delay_before_tool
        self.cancelled = False
        self.events_produced = 0
        self.last_history: list = []
        self.last_prompt: str = ""

    async def run(self, prompt, **kwargs):
        handler = kwargs.get("event_stream_handler")
        assert handler is not None
        event_stream_handler = handler
        self.last_history = list(kwargs.get("message_history") or [])
        self.last_prompt = prompt

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
                    await asyncio.sleep(3600)
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise
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

        await event_stream_handler(SimpleNamespace(), events())

        if self.mode == "deferred":
            return SimpleNamespace(
                output=DeferredToolRequests(
                    calls=[ToolCallPart(tool_name="get_schema", args="{}")]
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
        "runtime.approval.orchestrator.get_session_store", lambda: store
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


@pytest.mark.asyncio
async def test_takeover_pause_cancels_internal_task():
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    agent = FakeAgent(mode="block")
    gen = run_agent_stream("hi", [], AppConfig(), agent=agent)

    seen, paused = await _collect_until(gen, "human_takeover_request")
    assert paused
    assert any(ev["type"] == "tool_result" for ev in seen)

    await gen.aclose()
    assert agent.cancelled


@pytest.mark.asyncio
async def test_old_run_produces_no_events_after_close():
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    agent = FakeAgent(mode="loop")
    gen = run_agent_stream("hi", [], AppConfig(), agent=agent)

    seen, paused = await _collect_until(gen, "human_takeover_request")
    assert paused

    count_at_close = agent.events_produced
    await gen.aclose()
    await asyncio.sleep(0.2)
    assert agent.events_produced == count_at_close


@pytest.mark.asyncio
async def test_normal_completion_not_cancelled():
    agent = FakeAgent(mode="complete")
    gen = run_agent_stream("hi", [], AppConfig(), agent=agent)

    events = []
    async for ev in gen:
        events.append(ev)

    types = [ev["type"] for ev in events]
    assert "run_end" in types
    assert "metadata" in types
    assert not agent.cancelled


@pytest.mark.asyncio
async def test_deferred_pause_cleanup():
    agent = FakeAgent(mode="deferred")
    gen = run_agent_stream("hi", [], AppConfig(), agent=agent)

    seen, deferred = await _collect_until(gen, "_deferred_tool_requests")
    assert deferred

    await gen.aclose()
    assert not agent.cancelled


@pytest.mark.asyncio
async def test_complete_route_rejects_wrong_run_id(monkeypatch, store):
    _patch_store(monkeypatch, store)
    from api.routes import browser_interact

    monkeypatch.setattr(browser_interact, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(browser_interact, "get_config", lambda: AppConfig())
    monkeypatch.setattr(
        browser_interact,
        "get_run_registry",
        lambda: _RegistryStub(
            SimpleNamespace(
                run_id="abc",
                orchestrator=SimpleNamespace(run_id="abc"),
            )
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await complete_human_takeover(
            TakeoverCompleteRequest(session_id="sess_1", result="x", run_id="wrong")
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_chat_sse_disconnect_keeps_run_alive(monkeypatch, store):
    """断连只丢订阅者：run 继续（agent 未取消），重挂 from_index=0 拿到完整序列。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id

    monkeypatch.setattr(chat_route, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(chat_route, "get_session_store", lambda: store)

    agent = FakeAgent(mode="complete", delay_before_tool=0.5)
    slot = _start_run(sid, agent)

    response = _sse_response(slot.bus, sid, 0)
    chunks: list[Any] = []

    async def consume():
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.2)
    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer

    # 断连不结束 run：注册表仍有槽位，agent 未被取消
    assert get_run_registry().get(sid) is not None
    assert not agent.cancelled

    # 重挂 from_index=0：拿到含 run_end 的完整序列
    reattach = await chat_route.attach_stream(sid, 0)
    seen: list[Any] = []
    async for chunk in reattach.body_iterator:
        seen.append(chunk)
    text = "".join(seen)
    assert "event: run_end" in text
    assert "data: [DONE]" in text

    # run 结束（run_end 终态）后 owner 注销槽位
    await _await_true(lambda: get_run_registry().get(sid) is None)











@pytest.mark.asyncio
async def test_cancel_route_stale_session_returns_error(monkeypatch, store):
    _patch_store(monkeypatch, store)
    from api.routes import browser_interact

    monkeypatch.setattr(browser_interact, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(browser_interact, "get_config", lambda: AppConfig())
    monkeypatch.setattr(
        browser_interact,
        "get_run_registry",
        lambda: _RegistryStub(None),
    )
    with pytest.raises(HTTPException) as exc:
        await browser_interact.cancel_takeover(
            browser_interact.TakeoverCancelRequest(
                session_id="stale_sess", run_id="abc"
            )
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cancel_route_run_mismatch_returns_409(monkeypatch, store):
    _patch_store(monkeypatch, store)
    from api.routes import browser_interact

    monkeypatch.setattr(browser_interact, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(browser_interact, "get_config", lambda: AppConfig())
    monkeypatch.setattr(
        browser_interact,
        "get_run_registry",
        lambda: _RegistryStub(
            SimpleNamespace(
                run_id="real-run",
                orchestrator=SimpleNamespace(
                    run_id="real-run",
                    cancel_takeover=lambda run_id="", reason="": {
                        "ok": False,
                        "error": "run_mismatch",
                        "status": "not_cancelled",
                    },
                ),
            )
        ),
    )
    with pytest.raises(HTTPException) as exc:
        await browser_interact.cancel_takeover(
            browser_interact.TakeoverCancelRequest(
                session_id="sess_1", run_id="wrong"
            )
        )
    assert exc.value.status_code == 409


def test_model_message_serialization_roundtrip_tool_parts(tmp_path):
    from pydantic_ai.messages import ModelResponse

    storage = tmp_path / "sessions"
    store = FileSessionStore(storage)
    session = store.create()
    session.add_model_messages([
        ModelRequest(parts=[
            ToolCallPart(tool_name="browser_click", args={"selector": "#a"}, tool_call_id="c1"),  # type: ignore[arg-type]
            ToolReturnPart(tool_name="browser_click", content="clicked", tool_call_id="c1"),
        ]),
        ModelResponse(parts=[TextPart(content="hello")]),
    ])
    store.save()

    reloaded = FileSessionStore(storage)
    loaded = reloaded.get(session.session_id)
    assert loaded is not None
    msgs = loaded.model_messages
    assert len(msgs) == 2
    first = msgs[0]
    assert isinstance(first, ModelRequest)
    assert isinstance(first.parts[0], ToolCallPart)
    assert first.parts[0].tool_name == "browser_click"
    assert first.parts[0].tool_call_id == "c1"
    assert isinstance(first.parts[1], ToolReturnPart)
    assert first.parts[1].content == "clicked"
    second = msgs[1]
    assert isinstance(second, ModelResponse)
    assert isinstance(second.parts[0], TextPart)
    assert second.parts[0].content == "hello"
