from __future__ import annotations

import json
import threading
from typing import Any

from core.logging_setup import get_logger
from runtime.middleware_probe import (
    _browser_launched,
    _current_page_url,
    _is_document_discovery,
    _page_has_filter_components,
    _same_domain,
    _target_url_from_prompt,
)
from schemas import ToolResult

logger = get_logger("tool_middleware")

_BLOCKED_TOOLS = {
    "browser_read",
}

_SWITCH_LABEL = (
    "[Middleware] {tool_name} call intercepted (document-extraction task — low-level browser tools not suitable). "
    "Automatically switched to {replacement} with args: {args}\n"
    "The result is final data — use it directly. If it does not meet the request, explain why to the user, "
    "or use browser_extract_links / crawl_webpage instead.\n\n{result}"
)

_REPEAT_LABEL = (
    "[Middleware] {tool_name} has been intercepted multiple times this turn — do not call it again.\n"
    "For web data, call browser_extract_links (supports document filtering / pagination / domain limits) or "
    "crawl_webpage; if the result does not meet the request, explain why to the user."
)

_NO_PYTHON_LABEL = (
    "[Middleware] python_sandbox_execute intercepted: browser/crawl tool results are already final data, "
    "no Python processing needed. Answer directly from the results; for extra computation, explain the need to the user."
)

_NO_PYTHON_REPEAT_LABEL = (
    "[Middleware] python_sandbox_execute intercepted repeatedly: answer directly from the final browser/crawl tool data, "
    "no Python processing needed."
)

_EMPTY_RESULT_MARKERS = (
    "no links found",
    "no elements found",
    "no items found",
    "link extraction failed",
    "crawl failed",
    "no response",
    "timed out",
    "request timed out",
)
# Filtering tasks: when the page exposes filter components, low-level DOM
# probing tools must not be used to construct filters — the detect/apply
# pipeline (browser_detect_filters → browser_apply_filter → browser_download)
# is the only sanctioned path. browser_read carries the former evaluate (js) and
# query (selector) modes: a js read is probed on any filter page, a selector read
# only once browser_detect_filters has run this round.

_FILTER_LABEL = (
    "[Middleware] {tool_name} intercepted: the current page exposes filter components. "
    "Filtering must go through the detect/apply pipeline: "
    "browser_detect_filters → browser_apply_filter → browser_download. "
    "Do not use browser_read to probe page structure to construct filters. "
    "Call browser_detect_filters to obtain the Filter Schema; if the detected capabilities are "
    "insufficient, re-run browser_detect_filters or tell the user the filter cannot be completed."
)

_FILTER_REPEAT_LABEL = (
    "[Middleware] {tool_name} has been intercepted repeatedly this round — do not call it again. "
    "Use the browser_detect_filters / browser_apply_filter pipeline, or tell the user the filter cannot be completed."
)

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

_UI_PROBE_LABEL = (
    "[Middleware] {tool_name} intercepted: this looks like a UI/structure probing script. "
    "Discover elements with browser_find (it returns ready-to-use selectors plus semantic labels), "
    "read text or values with browser_read (selector + attribute=\"value\"), and act with "
    "browser_click / browser_fill / browser_select_option. browser_read js is reserved for native "
    "state the standard tools cannot reach (pure computation, canvas pixels, localStorage, navigator)."
)

_UI_PROBE_REPEAT_LABEL = (
    "[Middleware] {tool_name} UI-probe script intercepted repeatedly this round — do not call it again. "
    "Use browser_find / browser_read instead."
)

# 重复 find 熔断：同一逻辑 run、同一页、同一导航修订、同一查询指纹已被成功回答过，
# 模型再发一次相同的 browser_find 只会得到同样结果——改用已经拿到的 ref。
_FIND_REPEAT_LABEL = (
    "[Middleware] browser_find intercepted: this exact query (same page, same navigation state, "
    "same text/role/scope) has already been answered in this run. Do not scan again — reuse the "
    "`ref` values already returned for this page and pass them to "
    "browser_click / browser_fill / browser_select_option. If the target is not among them, change "
    "the query (text / role / scope) instead of repeating it."
)

_lock = threading.Lock()
_round_blocks: dict[str, dict[str, int]] = {}
_round_browser_used: set[str] = set()
_round_detect_used: set[str] = set()       # rounds where browser_detect_filters already ran
# 每次成功的 browser_find 记录，按 _run_key 归组；条目见 record_find。
_round_finds: dict[str, list[dict[str, Any]]] = {}

_MAX_ROUNDS = 1000


def _is_browser_tool(tool_name: str) -> bool:
    return tool_name.startswith("browser_")


def _round_key(ctx) -> str:
    return getattr(ctx, "run_id", None) or "default-round"


def _run_key(ctx) -> str:
    """一次逻辑 run 的稳定身份。

    取 ``ctx.deps.run_id``（由 lifecycle 在每次 agent.run 前写入 RunTracker 的 run_id，
    贯穿审批暂停/恢复的续跑循环），退化到 pydantic 的 ``ctx.run_id``（每次 agent.run 都会
    变，仅作兜底）。不要复用 ``_round_key``。
    """
    deps = getattr(ctx, "deps", None)
    run_id = getattr(deps, "run_id", None) if deps is not None else None
    if run_id:
        return str(run_id)
    return getattr(ctx, "run_id", None) or "default-round"


def _manager():
    from browser import get_manager

    return get_manager()


def _page_key(manager) -> str:
    """当前活动页身份；无页面返回 ``""``（上层 fail-open）。"""
    try:
        page = manager.page()
    except Exception:
        return ""
    return str(id(page)) if page is not None else ""


def _nav_revision(manager) -> int:
    """当前活动页的导航修订计数；读取失败按 0 处理。"""
    try:
        return int(manager.nav_revision())
    except Exception:
        return 0


def _page_url(manager) -> str:
    """当前活动页 URL；无页面返回 ``""``。"""
    try:
        page = manager.page()
    except Exception:
        return ""
    return (getattr(page, "url", "") or "") if page is not None else ""


def _normalize_query_part(value: Any) -> str:
    """归一化 browser_find 的 text / role：折叠连续空白并小写。"""
    return " ".join(str(value or "").split()).lower()


def _find_fingerprint(text: str, role: str, scope: str) -> str:
    """把 browser_find 的查询参数组装为稳定指纹。

    ``text`` / ``role`` 归一化（去首尾空白、折叠连续空白、小写），使同一意图的
    大小写 / 空白变体归为同一条；``scope`` 保留原值 —— visible / container / page
    语义不同，合并会误拦合法的扩大重扫。
    """
    return f"{scope}||{_normalize_query_part(role)}||{_normalize_query_part(text)}"


def record_find(
    ctx,
    *,
    page_key: str,
    page_url: str,
    nav_rev: int,
    fingerprint: str,
    produced: bool,
) -> None:
    """记录一次 browser_find 的结果（由工具层在产出 ref 后回写）。"""
    run_key = _run_key(ctx)
    with _lock:
        if len(_round_finds) > _MAX_ROUNDS:
            _round_finds.clear()
        _round_finds.setdefault(run_key, []).append({
            "page_key": page_key,
            "page_url": page_url,
            "nav_rev": nav_rev,
            "fingerprint": fingerprint,
            "produced": produced,
        })


def clear_run(run_key: str) -> None:
    """run 终结时清理该 run 的 find 记录，避免跨 run 累积。"""
    with _lock:
        _round_finds.pop(run_key, None)


def _is_repeat_find(ctx, args: dict | None) -> bool:
    """同一 run / 页 / 导航修订 / 查询指纹上是否已有成功 find 记录。

    不确定（取不到 run 或 page）一律返回 ``False``（fail-open）。
    """
    run_key = _run_key(ctx)
    if not run_key:
        return False
    try:
        manager = _manager()
    except Exception:
        return False
    page_key = _page_key(manager)
    if not page_key:
        return False
    page_url = _page_url(manager)
    nav_rev = _nav_revision(manager)

    raw_mode = args.get("mode") if isinstance(args, dict) else None
    mode = (str(raw_mode) if raw_mode else "elements").strip().lower()
    if mode != "elements":
        # containers 模式是另一种查询，且不产出 ref，不参与熔断。
        return False

    text = str(args.get("text") or "") if isinstance(args, dict) else ""
    role = str(args.get("role") or "") if isinstance(args, dict) else ""
    raw_scope = args.get("scope") if isinstance(args, dict) else None
    scope = (str(raw_scope) if raw_scope else "visible").strip().lower()
    if scope not in ("visible", "container", "page"):
        scope = "visible"
    fingerprint = _find_fingerprint(text, role, scope)

    with _lock:
        records = list(_round_finds.get(run_key, ()))
    for record in records:
        if not record.get("produced"):
            continue
        if (
            record.get("page_key") == page_key
            and record.get("nav_rev") == nav_rev
            and record.get("page_url") == page_url
            and record.get("fingerprint") == fingerprint
        ):
            return True

    # 弱命中：同一 run / 页 / 导航修订 / URL，text+role 归一化后相同、两次均
    # produced，仅 scope 不同 → 仍是同一意图的重复重扫（模型常把 scope 升级
    # visible → container → page 当重试阶梯）。page_url / nav_rev 变化仍放行。
    scope_fingerprints = {
        _find_fingerprint(text, role, candidate_scope)
        for candidate_scope in ("visible", "container", "page")
    }
    for record in records:
        if not record.get("produced"):
            continue
        if (
            record.get("page_key") == page_key
            and record.get("nav_rev") == nav_rev
            and record.get("page_url") == page_url
            and record.get("fingerprint") in scope_fingerprints
        ):
            return True
    return False


def _bump_round_block(round_id: str, tool_name: str) -> int:
    global _round_blocks
    with _lock:
        if len(_round_blocks) > _MAX_ROUNDS:
            _round_blocks = {}
        counters = _round_blocks.setdefault(round_id, {})
        counters[tool_name] = counters.get(tool_name, 0) + 1
        return counters[tool_name]


def _mark_browser_used(round_id: str) -> None:
    with _lock:
        if len(_round_browser_used) > _MAX_ROUNDS:
            _round_browser_used.clear()
        _round_browser_used.add(round_id)


def _js_allowlisted(js: str) -> bool:
    """纯计算 / 读原生浏览器状态的脚本：放行（escape hatch）。"""
    low = js.lower()
    return any(token in low for token in _UI_PROBE_ALLOWLIST)


def _looks_like_ui_probe(js: str) -> bool:
    """脚本是否带 DOM 结构探测指纹（查选择器 / 读 value / 枚举节点 / 读面板结构）。"""
    low = js.lower()
    return any(token in low for token in _UI_PROBE_FINGERPRINTS)


def _find_tool_func(name: str):
    from tools.tool_decorators import get_all_tool_defs

    for tool_def in get_all_tool_defs():
        if tool_def.name == name:
            return tool_def.func
    return None


def _label(tool_name: str, replacement: str, kwargs: dict, result: Any) -> str:
    if isinstance(result, dict):
        result = json.dumps(result, ensure_ascii=False)
    return _SWITCH_LABEL.format(
        tool_name=tool_name,
        replacement=replacement,
        args=json.dumps(kwargs, ensure_ascii=False),
        result=result,
    )


def _result_is_empty(result: Any) -> bool:
    if isinstance(result, ToolResult):
        return not result.success
    if isinstance(result, dict):
        return not result.get("rows") and not result.get("links")
    low = str(result).lower()
    return any(marker in low for marker in _EMPTY_RESULT_MARKERS)


def _browser_extract_kwargs(tool_name: str, args: dict, current_url: str) -> dict:
    """Synthesize params for the browser_extract_links switch.

    Only session-derived, harmless params are synthesized (metadata + site
    pagination). Task-constraint params (domain policy, document filter,
    selectors) are inherited from the original call when present — never
    hard-bound to the current page.
    """
    kwargs: dict = {"include_metadata": True, "max_pages": 5, "resolve_redirects": True}
    if tool_name == "browser_extract_links":
        inherit = ("selector", "wait_for_selector", "pagination_next_selector",
                   "allowed_domains", "document_domains", "document_only")
    else:
        inherit = ()
    for key in inherit:
        if args.get(key):
            kwargs[key] = args[key]
    return kwargs


async def evaluate_call(ctx, tool_name: str, args: dict | None = None) -> str:
    """Decide whether a tool call may execute.

    Returns one of:
    - "allow":      execute normally
    - "switch":     block and auto-switch to a more appropriate tool
    - "repeat":     block; same tool already blocked this round — do not run anything
    - "no-python":  block; browser control task forbids python_sandbox_execute
    - "filter-block"/"filter-repeat": block; page exposes an interactive filtering UI
    - "ui-probe-block"/"ui-probe-repeat": block; DOM/UI probing script on an interactive page
    - "find-repeat":  block; the same browser_find query already succeeded on this page state

    ``args`` carries the tool kwargs so a ``browser_read`` call's ``js`` can be
    fingerprinted; scripts reading native state (localStorage / navigator / canvas …)
    are allowlisted and pass through.

    Fails open: any uncertainty → "allow".
    """
    if ctx is None or getattr(ctx, "deps", None) is None:
        return "allow"
    round_id = _round_key(ctx)
    if _is_browser_tool(tool_name):
        _mark_browser_used(round_id)

    if tool_name == "browser_detect_filters":
        _round_detect_used.add(round_id)

    js = args.get("js") if isinstance(args, dict) else ""
    allowlisted = bool(js) and _js_allowlisted(js)
    read_js = tool_name == "browser_read" and bool(js and js.strip())
    read_selector = (
        tool_name == "browser_read"
        and not read_js
        and isinstance(args, dict)
        and bool(str(args.get("selector") or "").strip())
    )

    # Pages exposing an interactive filtering UI: low-level probing tools must not
    # be used to construct filters or probe page structure — the detect/apply
    # pipeline (and browser_find) is the sanctioned path.
    if read_js or (read_selector and round_id in _round_detect_used):
        if not allowlisted and await _page_has_filter_components():
            count = _bump_round_block(round_id, tool_name)
            if read_js and _looks_like_ui_probe(js):
                logger.info(
                    "tool middleware: blocking %s (ui-probe #%d) — DOM probing on interactive page",
                    tool_name, count,
                )
                return "ui-probe-repeat" if count >= 2 else "ui-probe-block"
            if count >= 2:
                return "filter-repeat"
            return "filter-block"

    if tool_name == "python_sandbox_execute":
        if round_id in _round_browser_used or _browser_launched():
            logger.info("tool middleware: blocking python_sandbox_execute — browser control active (round %s)", round_id)

    if tool_name == "browser_find":
        if _is_repeat_find(ctx, args):
            logger.info("tool middleware: blocking browser_find (find-repeat) — run %s", _run_key(ctx))
            return "find-repeat"
        return "allow"

    if tool_name not in _BLOCKED_TOOLS:
        return "allow"
    if not _is_document_discovery(ctx):
        return "allow"
    if not (_target_url_from_prompt(ctx) or _current_page_url()):
        return "allow"
    count = _bump_round_block(round_id, tool_name)
    logger.info("tool middleware: blocking %s (round block #%d) — document discovery detected", tool_name, count)
    if count >= 2:
        return "repeat"
    return "switch"


async def execute_switch(ctx, tool_name: str, args: dict, decision: str) -> str:
    """Execute the middleware action for a blocked tool call."""
    if decision == "no-python":
        return _NO_PYTHON_LABEL
    if decision == "no-python-repeat":
        return _NO_PYTHON_REPEAT_LABEL
    if decision == "filter-block":
        return _FILTER_LABEL.format(tool_name=tool_name)
    if decision == "filter-repeat":
        return _FILTER_REPEAT_LABEL.format(tool_name=tool_name)
    if decision == "ui-probe-block":
        return _UI_PROBE_LABEL.format(tool_name=tool_name)
    if decision == "ui-probe-repeat":
        return _UI_PROBE_REPEAT_LABEL.format(tool_name=tool_name)
    if decision == "find-repeat":
        return _FIND_REPEAT_LABEL

    current = _current_page_url()
    target = _target_url_from_prompt(ctx)

    if current and (not target or _same_domain(current, target)):
        replacement = "browser_extract_links"
        kwargs = _browser_extract_kwargs(tool_name, args, current)
    elif target:
        replacement = "crawl_webpage"
        kwargs = {
            "url": target,
            "max_pages": 5,
        }
    else:
        return await _run_original(ctx, tool_name, args)

    func = _find_tool_func(replacement)
    if func is None:
        return await _run_original(ctx, tool_name, args)

    inner = await func(ctx, **kwargs)
    if _result_is_empty(inner):
        logger.info(
            "tool middleware: switch result empty for %s (round %s) — falling back to original call",
            tool_name,
            _round_key(ctx),
        )
        original = await _run_original(ctx, tool_name, args)
        return (
            f"[Middleware] {tool_name} intercepted and switched to {replacement}, but the result was empty — "
            f"fell back to the original call.\n\n{original}"
        )
    return _label(tool_name, replacement, kwargs, inner)


async def _run_original(ctx, tool_name: str, args: dict) -> str:
    func = _find_tool_func(tool_name)
    if func is None:
        return f"[Middleware] {tool_name} switch failed: neither the replacement nor the original tool is available"
    return await func(ctx, **args)
