from __future__ import annotations

import asyncio
from contextlib import suppress
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
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
from runtime.approval_orchestrator import ApprovalOrchestrator
from api.routes.browser_interact import (
    TakeoverCompleteRequest,
    complete_human_takeover,
)
from api.routes.chat import (
    _active_orchestrators,
    _stream_orchestrator_events,
    get_orchestrator,
)
from runtime.session_file_store import FileSessionStore


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
        "get_orchestrator",
        lambda sid: SimpleNamespace(run_id="abc"),
    )

    with pytest.raises(HTTPException) as exc:
        await complete_human_takeover(
            TakeoverCompleteRequest(session_id="sess_1", result="x", run_id="wrong")
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_chat_sse_disconnect_terminates_running_run(monkeypatch, store):
    _patch_store(monkeypatch, store)
    sid = store.create().session_id

    agent = FakeAgent(mode="block", delay_before_tool=5.0)
    orchestrator = ApprovalOrchestrator(sid, AppConfig(), agent=agent)
    _active_orchestrators[sid] = orchestrator

    response = await _stream_orchestrator_events(orchestrator, "hi", [], sid)
    chunks: list[Any] = []

    async def consume():
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.2)
    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer

    assert get_orchestrator(sid) is None
    await _await_true(lambda: agent.cancelled)
    assert agent.cancelled











@pytest.mark.asyncio
async def test_cancel_route_stale_session_returns_error(monkeypatch, store):
    _patch_store(monkeypatch, store)
    from api.routes import browser_interact

    monkeypatch.setattr(browser_interact, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(browser_interact, "get_config", lambda: AppConfig())
    monkeypatch.setattr(
        browser_interact,
        "get_orchestrator",
        lambda sid: None,
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
        "get_orchestrator",
        lambda sid: SimpleNamespace(run_id="real-run", cancel_takeover=lambda run_id="", reason="": {"ok": False, "error": "run_mismatch", "status": "not_cancelled"}),
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
