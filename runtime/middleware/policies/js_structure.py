"""browser_read 用 js 枚举 DOM / 表单结构 → 引导改走 browser_find 与表单读。

命中「``querySelectorAll`` 遍历 + ``input`` / ``label`` / ``select`` / ``textarea``
结构关键词」的 js 读时拦下并提示用 ``browser_find`` 或 ``browser_read(form=True)``。
``js`` 的合法用途（canvas / localStorage / 纯计算）由 allowlist 放行，不在判定内；
页面存在可交互筛选组件时由 :class:`FilterPipelinePolicy` 先行处理。
"""

from __future__ import annotations

from core.logging_setup import get_logger
from runtime.middleware import context as ctxmod
from runtime.middleware.policies.filter_pipeline import _js_allowlisted
from runtime.middleware.state import STATE

logger = get_logger("tool_middleware")

_STRUCTURE_KEYWORDS = ("input", "label", "select", "textarea")


def _looks_like_structure_enum(js: str) -> bool:
    """脚本是否在枚举表单 / DOM 结构（遍历 + 表单结构关键词）。"""
    low = js.lower()
    if "queryselectorall" not in low:
        return False
    return any(keyword in low for keyword in _STRUCTURE_KEYWORDS)


class JsStructureSwitchPolicy:
    """拦截用 browser_read js 枚举表单 / DOM 结构的调用。"""

    name = "js-structure"

    async def evaluate(self, ctx, tool_name: str, args: dict | None) -> str | None:
        if tool_name != "browser_read" or not isinstance(args, dict):
            return None
        js = args.get("js") or ""
        if not _looks_like_structure_enum(js) or _js_allowlisted(js):
            return None
        round_id = ctxmod._round_key(ctx)
        count = STATE.bump_block(round_id, tool_name)
        logger.info(
            "tool middleware: blocking %s (js-structure #%d) — DOM structure enumeration",
            tool_name, count,
        )
        if count >= 2:
            return "ui-probe-repeat"
        return "ui-probe-block"
