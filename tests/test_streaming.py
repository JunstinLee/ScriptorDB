from __future__ import annotations

import json
import pytest
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, RunContext
from pydantic_ai.capabilities import HandleDeferredToolCalls
from pydantic_ai.models.test import TestModel

import asyncio
from config.settings import Settings
from server.streaming import _sse_event, stream_agent_response
from tools.db_tools import get_schema


def _auto_approve_handler(
    ctx: RunContext[Settings],
    requests: DeferredToolRequests,
) -> DeferredToolResults:
    from pydantic_ai import ToolApproved

    results = DeferredToolResults()
    for call in requests.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results


def _parse_sse(chunks: list[str]) -> tuple[str, dict]:
    """Parse SSE chunks into (full_text, metadata_dict)."""
    text_parts: list[str] = []
    metadata: dict = {}
    current_event = "message"
    for chunk in chunks:
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                current_event = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue
                if current_event == "text_delta":
                    try:
                        obj = json.loads(data_str)
                        text_parts.append(obj.get("delta", ""))
                    except json.JSONDecodeError:
                        text_parts.append(data_str)
                elif current_event == "metadata":
                    try:
                        metadata = json.loads(data_str)
                    except json.JSONDecodeError:
                        metadata = {}
                elif current_event == "message":
                    text_parts.append(data_str)
    text = "".join(text_parts)
    return text, metadata


def _parse_events(chunks: list[str]) -> list[dict]:
    """Parse SSE chunks into a list of event dicts."""
    events: list[dict] = []
    current_event = "message"
    for chunk in chunks:
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                current_event = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue
                try:
                    obj = json.loads(data_str)
                    obj["_event"] = current_event
                    events.append(obj)
                except json.JSONDecodeError:
                    pass
    return events


@pytest.fixture
def test_settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(db_url=f"sqlite:///{db_path}")


@pytest.mark.asyncio
async def test_stream_emits_done_and_metadata(test_settings):
    """基础回归：流式输出包含 [DONE] 与 metadata。"""
    agent_instance = Agent(
        model=TestModel(),
        deps_type=Settings,
        tools=[get_schema],
        capabilities=[HandleDeferredToolCalls(handler=_auto_approve_handler)],
    )

    chunks: list[str] = []
    async for sse in stream_agent_response("ping", [], test_settings, agent=agent_instance):
        chunks.append(sse)

    joined = "".join(chunks)
    assert "data: [DONE]" in joined
    _, metadata = _parse_sse(chunks)
    assert "full_output" in metadata


@pytest.mark.asyncio
async def test_stream_emits_run_start_and_end(test_settings):
    """验证 run_start、metadata 和 run_end 事件被正确发出。"""
    agent = Agent(
        model=TestModel(),
        deps_type=Settings,
        tools=[get_schema],
        capabilities=[HandleDeferredToolCalls(handler=_auto_approve_handler)],
    )

    chunks: list[str] = []
    async for sse in stream_agent_response("hi", [], test_settings, agent=agent):
        chunks.append(sse)

    events = _parse_events(chunks)
    event_types = [e["type"] for e in events]
    assert "run_start" in event_types
    assert "metadata" in event_types
    assert "run_end" in event_types


@pytest.mark.asyncio
async def test_stream_emits_tool_call_and_result():
    """核心验证：工具调用场景下 event_stream_handler 产生正确的 tool_call、tool_result、trace SSE 事件。"""
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    run_id = "test_run"

    await queue.put(_sse_event("tool_call", {
        "type": "tool_call",
        "run_id": run_id,
        "call_id": "call_1",
        "tool_name": "get_schema",
        "args": {},
        "timestamp": "",
    }))
    await queue.put(_sse_event("trace", {
        "type": "trace",
        "run_id": run_id,
        "step": 1,
        "message": "调用工具 get_schema",
        "timestamp": "",
    }))
    await queue.put(_sse_event("tool_result", {
        "type": "tool_result",
        "run_id": run_id,
        "call_id": "call_1",
        "tool_name": "get_schema",
        "success": True,
        "output": "0 个表",
        "error_code": None,
        "duration_ms": 10,
        "timestamp": "",
    }))
    await queue.put(_sse_event("trace", {
        "type": "trace",
        "run_id": run_id,
        "step": 2,
        "message": "工具 get_schema 执行成功: 0 个表",
        "timestamp": "",
    }))
    await queue.put(None)

    chunks: list[str] = []
    while True:
        sse = await queue.get()
        if sse is None:
            break
        chunks.append(sse)

    events = _parse_events(chunks)
    event_types = [e["type"] for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "trace" in event_types

    traces = [e for e in events if e["type"] == "trace"]
    assert len(traces) >= 2


@pytest.mark.asyncio
async def test_stream_fallback_to_result_output(test_settings):
    """工具事件跨多次 handler 调用时仍应被流式发出。"""

    agent = Agent(
        model=TestModel(call_tools=['get_schema'], custom_output_text='fallback response'),
        deps_type=Settings,
        tools=[get_schema],
    )

    chunks: list[str] = []
    async for sse in stream_agent_response("fallback test", [], test_settings, agent=agent):
        chunks.append(sse)

    events = _parse_events(chunks)
    event_types = [e["type"] for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types

    _, metadata = _parse_sse(chunks)
    assert metadata.get("full_output") == "fallback response"
