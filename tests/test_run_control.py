from __future__ import annotations

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel

from config.settings import Settings
from services.run_control import build_output_validator, extract_result_markers, should_allow_end

_MARKERS_MSG = ModelRequest(
    parts=[
        ToolReturnPart(
            tool_name="get_data",
            content={
                "total": 50,
                "rows": [
                    {
                        "text": "Form 4 July 28, 2026",
                        "links": ["https://d18rn0p25nwr6d.cloudfront.net/x.pdf"],
                    }
                ],
            },
            tool_call_id="1",
        )
    ]
)

_PLAIN_MSG = ModelRequest(parts=[])


def test_extract_markers_from_dict():
    markers = extract_result_markers([_MARKERS_MSG])
    assert "50" in markers
    assert "form 4" in markers
    assert "july 28, 2026" in markers
    assert "d18rn0p25nwr6d.cloudfront.net" in markers


def test_extract_markers_empty_messages():
    assert extract_result_markers(None) == set()
    assert extract_result_markers([]) == set()


@pytest.mark.parametrize(
    ("output", "messages", "expected", "kwargs"),
    [
        ("结果共有 50 条，日期是 July 28, 2026。", [_MARKERS_MSG], True, {}),
        ("提取到 50 条记录，Form 4。", [_MARKERS_MSG], True, {}),
        ("来源 d18rn0p25nwr6d.cloudfront.net，共 50 条。", [_MARKERS_MSG], True, {}),
        ("让我用 Python 来解析并格式化这些数据。", [_MARKERS_MSG], False, {}),
        ("好的，我已经完成查询。", [_MARKERS_MSG], False, {}),
        ("", [_MARKERS_MSG], False, {}),
        ("可以。", [_PLAIN_MSG], True, {}),
        ("可以。", None, True, {}),
        ("任意", [_MARKERS_MSG], True, {"partial_output": True}),
        ({"not": "str"}, [_MARKERS_MSG], True, {}),
        ("任何文本", [_MARKERS_MSG], True, {"retry": 1}),
    ],
)
def test_should_allow_end(output, messages, expected, kwargs):
    assert should_allow_end(output, messages=messages, **kwargs) is expected


def _tool_agent(handler):
    def get_data(ctx: RunContext[Settings]):
        return {"total": 50, "rows": [{"text": "Form 4 July 28, 2026"}]}

    agent = Agent(
        model=FunctionModel(handler),
        deps_type=Settings,
        output_type=str,
        tools=[get_data],
        retries={"output": 2},
    )
    agent.output_validator(build_output_validator())
    return agent


@pytest.mark.asyncio
async def test_run_rejects_narration_then_accepts_result():
    calls = []

    def handler(messages, info):
        calls.append(1)
        if len(calls) == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name="get_data", args={})])
        if len(calls) == 2:
            return ModelResponse(parts=[TextPart("让我用 Python 来解析这些数据。")])
        return ModelResponse(parts=[TextPart("结果共有 50 条记录，Form 4。")])

    agent = _tool_agent(handler)
    result = await agent.run("抓取数据", deps=Settings(db_url="sqlite:///:memory:"))
    assert result.output == "结果共有 50 条记录，Form 4。"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_run_accepts_result_immediately():
    calls = []

    def handler(messages, info):
        calls.append(1)
        if len(calls) == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name="get_data", args={})])
        return ModelResponse(parts=[TextPart("50 条记录，Form 4。")])

    agent = _tool_agent(handler)
    result = await agent.run("抓取数据", deps=Settings(db_url="sqlite:///:memory:"))
    assert result.output == "50 条记录，Form 4。"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_run_plain_qa_without_tools():
    calls = []

    def handler(messages, info):
        calls.append(1)
        return ModelResponse(parts=[TextPart("好的。")])

    agent = _tool_agent(handler)
    result = await agent.run("你好", deps=Settings(db_url="sqlite:///:memory:"))
    assert result.output == "好的。"
    assert len(calls) == 1
