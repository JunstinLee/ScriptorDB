from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, RunContext
from pydantic_ai.capabilities import HandleDeferredToolCalls
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from config.settings import Settings
from server.streaming import stream_agent_response
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
async def test_stream_emits_tool_call_and_result(test_settings):
    """核心验证：工具调用场景下必须出现 tool_call、tool_result、trace 和 run_end 事件。"""

    def fn(messages: list[Any], info: AgentInfo) -> ModelResponse:
        already_called = any(
            isinstance(m, ModelRequest)
            and any(isinstance(p, ToolReturnPart) for p in m.parts)
            for m in messages
        )
        if already_called:
            return ModelResponse(
                parts=[TextPart(content="已查完 schema，继续回复。")]
            )
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="get_schema",
                    args={},
                    tool_call_id="call_1",
                )
            ]
        )

    agent = Agent(
        model=FunctionModel(fn),
        deps_type=Settings,
        tools=[get_schema],
        capabilities=[HandleDeferredToolCalls(handler=_auto_approve_handler)],
    )

    chunks: list[str] = []
    async for sse in stream_agent_response("看看", [], test_settings, agent=agent):
        chunks.append(sse)

    events = _parse_events(chunks)
    event_types = [e["type"] for e in events]

    assert "run_start" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "trace" in event_types
    assert "metadata" in event_types
    assert "run_end" in event_types

    traces = [e for e in events if e["type"] == "trace"]
    assert len(traces) >= 2
