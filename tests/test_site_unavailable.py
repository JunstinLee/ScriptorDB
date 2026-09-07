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


# ---------- 分类器：正例 ----------


@pytest.mark.parametrize(
    "text",
    [
        "Navigation failed: net::ERR_NAME_NOT_RESOLVED at https://thedummysite.com",
        "HTTP 502 Bad Gateway",
        "Crawl failed: 503 Service Unavailable",
        "Navigation failed: ERR_CONNECTION_REFUSED",
        "Download failed: net::ERR_CONNECTION_TIMED_OUT",
        "crawl failed: getaddrinfo failed",
        "connect: connection refused",
        "proxy connection failed: ERR_PROXY_CONNECTION_FAILED",
    ],
)
def test_detect_matches_site_unavailable(text: str):
    detail = detect_site_unavailable("browser_navigate", text)
    assert detail  # 命中并返回 detail


def test_detect_detects_within_tool_result_struct():
    """ToolResult 结构内容递归提取（output / error.message / data）。"""
    tr = ToolResult(
        success=False,
        error=ToolErrorInfo(category="internal_error", message="Internal error (ID: x)"),
        data={"inner": "Crawl failed: 502 Bad Gateway from upstream"},
    )
    assert detect_site_unavailable("crawl_webpage", tr)


# ---------- 分类器：负例 ----------


@pytest.mark.parametrize(
    "text",
    [
        "HTTP 404 Not Found",                    # 页面级：站点可达
        "HTTP 429 Too Many Requests",            # 限流：站点在线
        "Navigation failed: ERR_ABORTED",        # 导航被取代
        "Request timed out after 10s",           # 工具自身超时
        "Click failed: element not visible",     # 页面交互错误
    ],
)
def test_detect_ignores_online_site_signals(text: str):
    assert detect_site_unavailable("browser_navigate", text) is None


def test_detect_ignores_non_network_tools():
    """非网络工具即使命中文本也不触发（数据库/文件工具永不中止）。"""
    assert detect_site_unavailable("query_database", "SELECT 502 rows") is None
    assert detect_site_unavailable("python_sandbox_execute", "err_connection_refused") is None
    assert detect_site_unavailable("write_csv", "bad gateway") is None


# ---------- 异常链查找 ----------


def test_find_site_unavailable_walks_chain():
    inner = SiteUnavailableError("The target website is unavailable: 502 Bad Gateway")
    wrapped = RuntimeError("wrapped") 
    wrapped.__cause__ = inner
    assert find_site_unavailable(wrapped) == "The target website is unavailable: 502 Bad Gateway"


def test_find_site_unavailable_none_for_other_errors():
    assert find_site_unavailable(RuntimeError("plain")) is None
    assert find_site_unavailable(SiteUnavailableError("")) == ""


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
