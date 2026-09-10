"""run/takeover 路由契约：run_id 校验、取消异常码、断连不影响 run。"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from api.routes import chat as chat_route
from api.routes.browser_interact import (
    TakeoverCompleteRequest,
    complete_human_takeover,
)
from config.app_config import AppConfig
from runtime.approval.run_registry import get_run_registry
from tests.support.ctx import await_true as _await_true
from tests.support.stubs import RegistryStub as _RegistryStub, patch_store as _patch_store
from tests.support.takeover import FakeAgent, start_run as _start_run


def _sse_response(run_slot, sid: str, from_index: int = 0) -> StreamingResponse:
    return StreamingResponse(
        chat_route._stream_bus(run_slot.bus, from_index, sid),
        media_type="text/event-stream",
    )


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

    response = _sse_response(slot, sid, 0)
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


