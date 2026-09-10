"""站点级不可用确定性中止的专项测试。

核心契约：
- 浏览器/爬取/下载工具结果命中网关/DNS/连接失败信号 → translator 抛出
  SiteUnavailableError，lifecycle 转 error 终态（不再产出后续工具事件）。
- 页面级 4xx/429/ERR_ABORTED/裸 timeout 及非网络工具不触发。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ToolCallPart,
    ToolReturnPart,
)

from config.app_config import AppConfig
from runtime.agent_runner import run_agent_stream
from runtime.runner.errors import SiteUnavailableError, find_site_unavailable
from runtime.site_unavailable import detect_site_unavailable
from schemas.tool import ToolErrorInfo, ToolResult


class FakeUnavailableAgent:
    """单次工具调用,内容由注入内容决定。模拟 pydantic-ai 对
    event_stream_handler 异常的透传。"""

    def __init__(self, tool_name: str, content: Any):
        self.tool_name = tool_name
        self.content = content

    async def run(self, prompt, **kwargs):
        handler = kwargs.get("event_stream_handler")
        assert handler is not None
        ctx = SimpleNamespace(deps=SimpleNamespace(workspace_id="ws"))

        async def events():
            yield FunctionToolCallEvent(
                part=ToolCallPart(
                    tool_name=self.tool_name, args="{}", tool_call_id="call_1"
                )
            )
            yield FunctionToolResultEvent(
                part=ToolReturnPart(
                    tool_name=self.tool_name,
                    content=self.content,
                    tool_call_id="call_1",
                )
            )

        try:
            await handler(ctx, events())
        except SiteUnavailableError:
            raise  # translator 抛出的中止信号原样透传
        return SimpleNamespace(
            output="ok",
            new_messages=lambda: [],
            all_messages=lambda: [],
        )


async def _collect_all(gen, timeout: float = 5.0):
    seen = []

    async def consume():
        async for ev in gen:
            seen.append(ev)

    await asyncio.wait_for(asyncio.create_task(consume()), timeout=timeout)
    return seen



# ---------- 生命周期终态 ----------


async def test_unavailable_aborts_run_with_error_terminal():
    """命中站点不可用 → error 终态（英文提示），随后 run_end；
    不再产出任何后续工具/文本事件。"""
    agent = FakeUnavailableAgent(
        "browser_navigate",
        "Navigation failed: net::ERR_NAME_NOT_RESOLVED thedummysite.com",
    )
    gen = run_agent_stream("打开网站", [], AppConfig(), agent=agent)

    events = await _collect_all(gen)

    types = [ev["type"] for ev in events]
    assert "tool_call" in types
    assert "tool_result" in types  # 失败结果先完整展示
    assert "trace" in types

    errors = [ev for ev in events if ev["type"] == "error"]
    assert len(errors) == 1
    assert "The target website is unavailable" in errors[0]["message"]
    assert "aborted automatically" in errors[0]["message"]
    assert "thedummysite.com" in errors[0]["message"]

    # 终态收敛：error 之后只有 run_end，无新工具/文本继续
    err_idx = types.index("error")
    assert types[err_idx + 1 :] == ["run_end"]


async def test_online_signal_run_completes_normally():
    """404/429 等站点在线信号不中止：run 正常完成。"""
    agent = FakeUnavailableAgent("browser_navigate", "HTTP 404 Not Found")
    gen = run_agent_stream("打开网站", [], AppConfig(), agent=agent)

    events = await _collect_all(gen)

    types = [ev["type"] for ev in events]
    assert "error" not in types
    assert types[-1] == "run_end"
