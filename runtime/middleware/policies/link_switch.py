"""browser_read 收集全页链接 → 改派 browser_extract_links。

命中「selector 为 ``a`` / ``a[href]`` + ``attribute`` 为 ``href`` + ``all``」这一
全页链接收集形态时，低层级读取会被拦下并改派专用工具；同轮重复命中退化为
「不要再重复调用」。
"""

from __future__ import annotations

from core.logging_setup import get_logger
from runtime.middleware import context as ctxmod
from runtime.middleware.state import STATE

logger = get_logger("tool_middleware")

_LINK_SELECTORS = {"a", "a[href]"}


class LinkSwitchPolicy:
    """拦截用 browser_read 收集全页链接的调用，改派 browser_extract_links。"""

    name = "link-switch"

    async def evaluate(self, ctx, tool_name: str, args: dict | None) -> str | None:
        if tool_name != "browser_read" or not isinstance(args, dict):
            return None
        if (args.get("js") or "").strip():
            return None
        if not args.get("all"):
            return None
        if str(args.get("attribute") or "").strip().lower() != "href":
            return None
        selector = str(args.get("selector") or "").strip().lower().replace(" ", "")
        if selector not in _LINK_SELECTORS:
            return None
        round_id = ctxmod._round_key(ctx)
        count = STATE.bump_block(round_id, tool_name)
        logger.info(
            "tool middleware: blocking %s (link-switch #%d) — full-page link collection",
            tool_name, count,
        )
        if count >= 2:
            return "link-repeat"
        return "switch"
