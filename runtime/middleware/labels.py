"""中间件拦截文案（英文，注入模型的替代动作说明）。

集中管理所有策略返回给模型的 label 模板，避免文案散落在判定逻辑里。
"""

from __future__ import annotations

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

_FIND_REPEAT_LABEL = (
    "[Middleware] browser_find intercepted: this exact query (same page, same navigation state, "
    "same text/role/scope) has already been answered in this run. Do not scan again — reuse the "
    "`ref` values already returned for this page and pass them to "
    "browser_click / browser_fill / browser_select_option. If the target is not among them, change "
    "the query (text / role / scope) instead of repeating it."
)
