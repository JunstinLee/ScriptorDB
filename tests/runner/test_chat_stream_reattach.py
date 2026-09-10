"""run 生存期与 SSE 订阅解耦的专项测试（阶段一根治）。

核心契约：
- 无订阅者时 run 仍走完并落盘（owner 持有生存期）。
- 重挂订阅按 `from_index` 游标增量重放，不重复已消费事件。
- 同一 session 第二个 `POST /chat` 返回 409（不静默覆盖前一个 run）。
- `GET /sessions/{id}/active-run` 在接管挂起时给出 run_id 与 suspended 标记。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any, cast

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
from runtime.approval.run_registry import get_run_registry
from runtime.session_file_store import FileSessionStore

from api.routes import chat as chat_route
from schemas import ChatRequest


class FakeAgent:
    """一把 browser 工具；block 模式下 tool result 后等 release / 取消。"""

    def __init__(self, block: bool = False) -> None:
        self.block = block
        self.release = False
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
            if self.block:
                try:
                    while not self.release:
                        await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise

        await handler(_Ctx(), events())
        return _Result()


class _Ctx:
    session_id = "test"
    run_id = ""

    def cancel(self) -> None:  # noqa: D102 - hook 取消路径需要
        pass

    async def enqueue(self, *content) -> None:  # noqa: D102
        pass


class _Result:
    output = "ok"

    def new_messages(self) -> list:
        return []

    def all_messages(self) -> list:
        return []


@pytest.fixture(autouse=True)
def _reset_state():
    mgr = get_manager()
    mgr.takeover.reset()
    registry = get_run_registry()
    yield
    mgr.takeover.reset()
    for session_id in list(_REGISTRY_SESSIONS):
        registry.remove(session_id)
    _REGISTRY_SESSIONS.clear()


_REGISTRY_SESSIONS: set[str] = set()


@pytest.fixture
def store(tmp_path):
    return FileSessionStore(tmp_path / "sessions")


def _patch_store(monkeypatch, store) -> None:
    monkeypatch.setattr("runtime.sessions.get_session_store", lambda: store)
    monkeypatch.setattr("services.chat_service.get_session_store", lambda: store)
    monkeypatch.setattr(
        "runtime.approval.orchestrator.get_session_store", lambda: store
    )


def _patch_chat(monkeypatch, store, agent: FakeAgent) -> None:
    monkeypatch.setattr(chat_route, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(chat_route, "get_config", lambda: AppConfig())
    monkeypatch.setattr(chat_route, "get_session_store", lambda: store)

    async def _augment(prompt: str, attachments=None, crawl_url=None) -> str:
        return prompt

    monkeypatch.setattr(chat_route, "augment_prompt", _augment)

    real_orchestrator = ApprovalOrchestrator

    def _factory(session_id: str, config: AppConfig, **kwargs):
        kwargs["agent"] = agent
        return real_orchestrator(session_id, config, **kwargs)

    monkeypatch.setattr(chat_route, "ApprovalOrchestrator", _factory)


async def _await_true(flag, timeout: float = 5.0) -> None:
    async def wait():
        while not flag():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=timeout)


def _track(sid: str) -> None:
    _REGISTRY_SESSIONS.add(sid)


async def _cancel_slot(sid: str) -> None:
    slot = get_run_registry().get(sid)
    if slot is None or slot.task is None:
        return
    slot.task.cancel()
    with suppress(asyncio.CancelledError):
        await slot.task


async def test_run_completes_and_persists_without_subscriber(monkeypatch, store):
    """无任何订阅者：owner 仍跑完 run 并落盘 completed 记录。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    _track(sid)
    _patch_chat(monkeypatch, store, FakeAgent(block=False))

    response = await chat_route.chat(sid, ChatRequest(prompt="hi"))
    assert response.media_type == "text/event-stream"

    await _await_true(lambda: get_run_registry().get(sid) is None)

    session = store.get(sid)
    assert session is not None
    assert any(r.status == "completed" for r in session.runs)


async def test_from_index_replays_incrementally(monkeypatch, store):
    """增量重挂：from_index=游标 只收到之后的事件，无重复。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    _track(sid)
    agent = FakeAgent(block=True)
    _patch_chat(monkeypatch, store, agent)

    await chat_route.chat(sid, ChatRequest(prompt="hi"))
    slot = get_run_registry().get(sid)
    assert slot is not None

    gen = slot.bus.subscribe(0)
    cursor: int | None = None
    async for index, event in gen:
        if event.get("type") == "tool_result":
            cursor = index + 1
            break
    await cast(AsyncGenerator[tuple[int, dict[str, Any]], None], gen).aclose()
    assert cursor is not None

    rest: list[tuple[int, str]] = []

    async def drain():
        async for index, event in slot.bus.subscribe(cursor):
            rest.append((index, event["type"]))

    consumer = asyncio.create_task(drain())
    agent.release = True
    await asyncio.wait_for(consumer, timeout=5.0)

    assert rest, "增量重挂应收到游标之后的事件"
    assert all(index >= cursor for index, _ in rest)
    assert rest[-1][1] == "run_end"
    assert "tool_result" not in [ev_type for _, ev_type in rest]


async def test_second_chat_request_conflicts(monkeypatch, store):
    """同一 session 已有活动 run：第二个 POST /chat 返回 409。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    _track(sid)
    _patch_chat(monkeypatch, store, FakeAgent(block=True))

    await chat_route.chat(sid, ChatRequest(prompt="first"))
    with pytest.raises(HTTPException) as exc:
        await chat_route.chat(sid, ChatRequest(prompt="second"))
    assert exc.value.status_code == 409

    await _cancel_slot(sid)


async def test_active_run_reports_takeover_suspension(monkeypatch, store):
    """接管挂起时 /active-run 返回 suspended=takeover 与正确 run_id。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    _track(sid)
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    _patch_chat(monkeypatch, store, FakeAgent(block=True))
    await chat_route.chat(sid, ChatRequest(prompt="hi"))
    slot = get_run_registry().get(sid)
    assert slot is not None

    await _await_true(lambda: mgr.takeover.state == HumanTakeoverState.WAITING_HUMAN)
    info = await chat_route.active_run(sid)
    assert info["suspended"] == "takeover"
    assert info["run_id"] == slot.run_id
    assert info["last_index"] > 0

    await _cancel_slot(sid)


async def test_active_run_empty_without_run(monkeypatch, store):
    """无活动 run：/active-run 返回空 run_id 与 0 游标，/stream 返回 404。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    monkeypatch.setattr(chat_route, "require_workspace", lambda: AppConfig())
    monkeypatch.setattr(chat_route, "get_session_store", lambda: store)

    info = await chat_route.active_run(sid)
    assert info == {"run_id": "", "suspended": None, "reason": "", "last_index": 0}

    with pytest.raises(HTTPException) as exc:
        await chat_route.attach_stream(sid, 0)
    assert exc.value.status_code == 404
