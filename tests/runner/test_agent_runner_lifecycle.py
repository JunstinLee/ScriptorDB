"""runner 生命周期：接管挂起、关闭后不再产事件、正常完成、deferred 清理。

路由契约用例见 test_runner_route_contracts.py；订阅重挂见 test_chat_stream_reattach.py。
"""

from __future__ import annotations

import asyncio

import pytest

from browser import get_manager
from config.app_config import AppConfig
from runtime.agent_runner import run_agent_stream
from tests.support.ctx import collect_until as _collect_until
from tests.support.takeover import FakeAgent


@pytest.fixture(autouse=True)
def _reset_takeover():
    mgr = get_manager()
    mgr.takeover.reset()
    yield
    mgr.takeover.reset()


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
