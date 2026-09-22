"""站点不可用分类器：文本/结构命中、在线信号负例、异常链查找。"""

from __future__ import annotations

import pytest

from runtime.runner.errors import SiteUnavailableError, find_site_unavailable
from runtime.site_unavailable import detect_site_unavailable
from schemas.tool import ToolErrorInfo, ToolResult


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


@pytest.mark.parametrize(
    "tool_name, text",
    [
        ("browser_evaluate", '{"url":"https://x/invoice-query","count":0,"bodyLen":502}'),  # 字节数
        ("browser_get_text", "发票金额 502.00"),                                             # 金额
        ("browser_navigate", 'Navigation failed: {"code":503}'),                             # JSON 字段值
    ],
)
def test_detect_ignores_bare_status_number(tool_name: str, text: str):
    """裸状态码数字（JSON 字段值、金额）不算网关错误，需带状态码上下文。"""
    assert detect_site_unavailable(tool_name, text) is None


def test_detect_matches_status_code_with_context():
    """带 HTTP 前缀的状态码仍触发（正则分支）。"""
    assert detect_site_unavailable("browser_navigate", "Navigation failed: HTTP 503")


def test_detect_ignores_read_only_browser_tools():
    """只读页面、操作页面的浏览器工具不再参与检测。"""
    assert detect_site_unavailable("browser_evaluate", "502 Bad Gateway") is None
    assert detect_site_unavailable("browser_get_text", "502 Bad Gateway") is None
    assert detect_site_unavailable("browser_query", "service unavailable") is None


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

