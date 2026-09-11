"""接管期间 SSE 订阅流与 run 生存期的关系。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.responses import StreamingResponse

from browser import get_manager
from config.app_config import AppConfig
from runtime.approval.orchestrator import ApprovalOrchestrator
from runtime.approval.run_registry import get_run_registry
from runtime.approval.store import get_takeover_checkpoint_store
from api.routes.chat import _stream_bus
from tests.support.ctx import await_true as _await_true
from tests.support.stubs import patch_store as _patch_store
from tests.support.takeover import FakeAgent, start_slot as _start_slot


@pytest.fixture(autouse=True)
def _reset_takeover():
    mgr = get_manager()
    mgr.takeover.reset()
    yield
    mgr.takeover.reset()


# ---------- SSE 流 ----------


async def test_chat_sse_takeover_pause_keeps_stream_open(monkeypatch, store):
    """接管期间订阅流保持打开；恢复后同一 run 的事件继续推送至 run_end。"""
    _patch_store(monkeypatch, store)
    sid = store.create().session_id
    mgr = get_manager()
    mgr.takeover.request_takeover("unit test", "unit", url="http://example.com")

    config = AppConfig()
    config.chat_session_id = sid
    agent = FakeAgent(mode="block")
    orchestrator = ApprovalOrchestrator(sid, config, agent=agent)
    slot = _start_slot(sid, orchestrator)

    response = StreamingResponse(
        _stream_bus(slot.bus, 0, sid), media_type="text/event-stream"
    )
    chunks: list[Any] = []

    async def consume():
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    consumer = asyncio.create_task(consume())
    await _await_true(lambda: any("human_takeover_request" in c for c in chunks))

    # 接管期间：订阅流保持打开，run 挂起未取消，槽位保留
    await asyncio.sleep(0.2)
    assert not consumer.done()
    assert not agent.cancelled
    assert get_run_registry().get(sid) is not None

    # 恢复：同一 run 继续，总线推送 run_end 后订阅结束
    mgr.takeover.complete("done")
    agent.release = True
    assert orchestrator.resume_takeover(orchestrator.run_id, "done")["ok"]
    await asyncio.wait_for(consumer, timeout=5.0)

    # run_end 终态收敛：owner 注销槽位，checkpoint 清理
    await _await_true(lambda: get_run_registry().get(sid) is None)
    assert get_takeover_checkpoint_store().get(sid) is None
