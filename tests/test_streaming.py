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
    text_parts: list[str] = []
    metadata: dict = {}
    for chunk in chunks:
        if chunk.startswith("data: "):
            data = chunk[len("data: "):]
            text_parts.append(data)
        elif chunk.startswith("event: metadata\ndata: "):
            try:
                metadata = json.loads(chunk.split("data: ", 1)[1].strip())
            except json.JSONDecodeError:
                metadata = {}
    text = "".join(p for p in text_parts if p != "[DONE]")
    return text, metadata


@pytest.fixture
def test_settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(db_url=f"sqlite:///{db_path}")


@pytest.mark.asyncio
async def test_stream_emits_done_and_metadata(test_settings):
    """基础回归：流式输出包含文本增量、[DONE] 与 metadata。"""
    m = FunctionModel(
        lambda messages, info: ModelResponse(parts=[TextPart(content="完成。")])
    )

    agent = Agent(
        model=m,
        deps_type=Settings,
        tools=[get_schema],
        capabilities=[HandleDeferredToolCalls(handler=_auto_approve_handler)],
    )

    chunks: list[str] = []
    async for sse in stream_agent_response("ping", [], test_settings):
        chunks.append(sse)

    joined = "".join(chunks)
    assert "data: [DONE]" in joined
    text, metadata = _parse_sse(chunks)
    assert "完成" in text
    assert metadata.get("full_output") == text


@pytest.mark.asyncio
async def test_stream_continues_text_after_tool_call(test_settings):
    """核心修复验证：第一轮请求调用工具后，第二轮的文本仍通过 SSE 推送。"""

    def make_model() -> FunctionModel:
        state = {"called": False}

        def fn(messages: list[Any], info: AgentInfo) -> ModelResponse:
            last_user_or_tool = messages[-1] if messages else None
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

        return FunctionModel(fn)

    agent = Agent(
        model=make_model(),
        deps_type=Settings,
        tools=[get_schema],
        capabilities=[HandleDeferredToolCalls(handler=_auto_approve_handler)],
    )

    chunks: list[str] = []
    async for sse in stream_agent_response("看看", [], test_settings):
        chunks.append(sse)

    text, metadata = _parse_sse(chunks)
    assert "已查完 schema" in text, f"第二轮文本没被推送: text={text!r}"
    assert "data: [DONE]" in "".join(chunks)
    assert metadata["full_output"] == text
