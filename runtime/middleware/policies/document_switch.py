"""文档提取任务拦截 browser_read，自动切换到 browser_extract_links / crawl_webpage。

任务被判为「文档发现」时，低层级 DOM 读取工具（browser_read）会被拦下并自动
改派到结构化链接提取或抓取工具；同一回合内重复命中则退化为「不要重复调用」。
"""

from __future__ import annotations

from core.logging_setup import get_logger
from runtime.middleware import context as ctxmod
from runtime.middleware.state import STATE
from runtime.middleware_probe import (
    _current_page_url,
    _is_document_discovery,
    _target_url_from_prompt,
)

logger = get_logger("tool_middleware")

_BLOCKED_TOOLS = {
    "browser_read",
}


class DocumentSwitchPolicy:
    """文档发现场景下拦 browser_read 并改派结构化工具。"""

    name = "document-switch"

    async def evaluate(self, ctx, tool_name: str, args: dict | None) -> str | None:
        if tool_name not in _BLOCKED_TOOLS:
            return None
        if not _is_document_discovery(ctx):
            return None
        if not (_target_url_from_prompt(ctx) or _current_page_url()):
            return None
        round_id = ctxmod._round_key(ctx)
        count = STATE.bump_block(round_id, tool_name)
        logger.info(
            "tool middleware: blocking %s (round block #%d) — document discovery detected",
            tool_name, count,
        )
        if count >= 2:
            return "repeat"
        return "switch"
