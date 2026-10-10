"""站点级不可用检测:导航/爬取/下载类工具结果命中网关错误、DNS 或连接失败时,
返回 detail,供 translator 中止流程。纯函数模块,零运行时依赖,便于单测。

刻意不匹配的语义(站点在线,不中止):
- 页面级 4xx(400/401/403/404/405)、限流 429 —— 站点可达,属授权/参数/频率问题;
- ERR_ABORTED —— 导航被后续动作取代,非宕机;
- 裸 "timeout"/"timed out" —— 工具自身超时,非站点不可达
  (net::ERR_TIMED_OUT / ERR_CONNECTION_TIMED_OUT 例外,属连接层失败)。
"""

from __future__ import annotations

import re
from typing import Any

from tools.tool_result import ToolResult

# 仅对发起网络请求的工具做检测;数据库/文件/图表等工具永不触发。
_NETWORK_ACTION_TOOLS = frozenset({
    "browser_navigate",
    "browser_go_back",
    "browser_go_forward",
    "browser_download",
    "crawl_webpage",
    "download_file",
})

# 站点级不可用信号(子串匹配,大小写不敏感)。
_GATEWAY_MARKERS = (
    "bad gateway",
    "service unavailable",
    "gateway timeout",
)

# 状态码需带上下文,避免 JSON 字段值(如 bodyLen":502)被当成网关错误。
_GATEWAY_CODE_RE = re.compile(r'(?<![":\w])(?:502|503|504)(?![\d.,}])')

_DNS_MARKERS = (
    "err_name_not_resolved",
    "getaddrinfo failed",
    "name or service not known",
)
_CONNECTION_MARKERS = (
    "err_connection_refused",
    "err_connection_reset",
    "err_connection_closed",
    "err_connection_timed_out",
    "err_address_unreachable",
    "err_internet_disconnected",
    "err_proxy_connection_failed",
    "err_timed_out",
    "net::err_",                  # 兜底所有 net::ERR_* 变体
    "connection refused",
    "failed to establish a new connection",
)
_ALL_MARKERS = _GATEWAY_MARKERS + _DNS_MARKERS + _CONNECTION_MARKERS

_MAX_DETAIL = 200


def _collect_texts(value: Any, out: list[str]) -> None:
    """递归收集内容中的全部文本:ToolResult 拆出 output/error.message/data。"""
    if isinstance(value, ToolResult):
        if value.output:
            out.append(value.output)
        if value.error and value.error.message:
            out.append(value.error.message)
        _collect_texts(value.data, out)
        return
    if isinstance(value, dict):
        for v in value.values():
            _collect_texts(v, out)
        return
    if isinstance(value, (list, tuple)):
        for v in value:
            _collect_texts(v, out)
        return
    if isinstance(value, str):
        out.append(value)


def _summarize(text: str, marker: str) -> str:
    """取命中 marker 所在行作为 detail,截断到 _MAX_DETAIL。"""
    low = text.lower()
    idx = low.find(marker.lower())
    if idx == -1:
        snippet = text
    else:
        start = text.rfind("\n", 0, idx) + 1
        end = text.find("\n", idx)
        snippet = text[start:end if end != -1 else len(text)].strip() or text
    if len(snippet) > _MAX_DETAIL:
        snippet = snippet[: _MAX_DETAIL - 3] + "..."
    return snippet


def detect_site_unavailable(tool_name: str, content: Any) -> str | None:
    """工具结果命中站点级不可用信号 → 返回 detail 摘要;否则返回 None。

    tool_name 决定门控:仅导航/爬取/下载类工具参与检测。
    """
    if tool_name not in _NETWORK_ACTION_TOOLS:
        return None
    texts: list[str] = []
    _collect_texts(content, texts)
    joined = "\n".join(t for t in texts if t)
    if not joined:
        return None
    low = joined.lower()
    for marker in _ALL_MARKERS:
        if marker in low:
            return _summarize(joined, marker)
    match = _GATEWAY_CODE_RE.search(joined)
    if match:
        return _summarize(joined, match.group(0))
    return None
