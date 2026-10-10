"""筛选页拦截：不得用 browser_read 的 js / selector 探测页面结构来构造筛选器。

页面暴露可交互筛选组件时，筛选必须走 detect/apply 管线
（browser_detect_filters → browser_apply_filter → browser_download）。
browser_read 携带 DOM 结构指纹的 js 脚本被归为「ui-probe」，纯计算 / 读原生
浏览器状态的脚本由 allowlist 放行。
"""

from __future__ import annotations

from core.logging_setup import get_logger
from runtime.middleware import context as ctxmod
from runtime.middleware.state import STATE
from runtime.middleware_probe import _page_has_filter_components

logger = get_logger("tool_middleware")

# UI discovery / probing evaluate：带 DOM 结构指纹的脚本 + 页面处于可操作 UI →
# 引导回工具路径。纯计算 / 读原生浏览器状态的脚本由 allowlist 放行。
_UI_PROBE_FINGERPRINTS = (
    "queryselector", "queryselectorall", "getboundingclientrect",
    "outerhtml", "innerhtml", "classlist", "classname",
    "getattribute(", "elementfrompoint", "nextsibling", "parentelement",
    "children.length",
)
_UI_PROBE_ALLOWLIST = (
    "localstorage", "sessionstorage", "indexeddb", "document.cookie",
    "navigator.", "performance.", "canvas", "getcontext(", "webgl",
    "devicepixelratio", "window.innerwidth", "window.innerheight",
    "matchmedia", "date.now", "math.", "json.", "crypto.",
    "fetch(", "xmlhttprequest",
)


def _js_allowlisted(js: str) -> bool:
    """纯计算 / 读原生浏览器状态的脚本：放行（escape hatch）。"""
    low = js.lower()
    return any(token in low for token in _UI_PROBE_ALLOWLIST)


def _looks_like_ui_probe(js: str) -> bool:
    """脚本是否带 DOM 结构探测指纹（查选择器 / 读 value / 枚举节点 / 读面板结构）。"""
    low = js.lower()
    return any(token in low for token in _UI_PROBE_FINGERPRINTS)


class FilterPipelinePolicy:
    """拦截在筛选页用 browser_read 探测结构的调用。"""

    name = "filter-pipeline"

    async def evaluate(self, ctx, tool_name: str, args: dict | None) -> str | None:
        js = args.get("js") if isinstance(args, dict) else ""
        allowlisted = bool(js) and _js_allowlisted(js)
        read_js = tool_name == "browser_read" and bool(js and js.strip())
        read_selector = (
            tool_name == "browser_read"
            and not read_js
            and isinstance(args, dict)
            and bool(str(args.get("selector") or "").strip())
        )
        round_id = ctxmod._round_key(ctx)
        if not (read_js or (read_selector and STATE.detect_was_used(round_id))):
            return None
        if allowlisted or not await _page_has_filter_components():
            return None

        count = STATE.bump_block(round_id, tool_name)
        if read_js and _looks_like_ui_probe(js):
            logger.info(
                "tool middleware: blocking %s (ui-probe #%d) — DOM probing on interactive page",
                tool_name, count,
            )
            return "ui-probe-repeat" if count >= 2 else "ui-probe-block"
        if count >= 2:
            return "filter-repeat"
        return "filter-block"
