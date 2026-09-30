from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from core.logging_setup import get_logger

logger = get_logger("middleware_probe")

# 文档提取类任务关键词；命中 ≥2 个视为文档发现（配合交互关键词豁免）。
_DOC_KEYWORDS = (
    "文档",
    "抓取",
    "爬取",
    "提取",
    "链接",
    "pdf",
    "excel",
    "zip",
    "csv",
    "download",
    "document",
    "crawl",
    "extract",
    "filing",
)

# 交互式任务（点击/填写/筛选/测试等）需要低层级 DOM 工具检查页面结构，
# 不属于"文档提取"，命中即豁免，避免把合法排查误拦成 browser_extract_links。
_INTERACTION_KEYWORDS = (
    "点击",
    "填写",
    "输入",
    "选择",
    "选中",
    "筛选",
    "过滤",
    "下拉",
    "测试",
    "切换",
    "click",
    "fill",
    "type",
    "select",
    "filter",
    "dropdown",
    "test",
    "choose",
)

_URL_PATH_SIGNALS = ("filings", "documents", "docs", "download", "archive")

_URL_RE = re.compile(r"https?://[^\s\"'<>，。；）)】\]}]+")

# url -> (记录时刻, 页面是否暴露筛选组件)。SPA 路由/弹窗状态会变化，
# 按 TTL 失效而不是永久按键锁定，避免弹层开合后判据失真。
_page_filter_cache: dict[str, tuple[float, bool]] = {}
_PAGE_FILTER_TTL = 30.0


def _browser_launched() -> bool:
    try:
        from browser import get_manager

        return get_manager().page() is not None
    except Exception:
        return False


def _current_page_url() -> str | None:
    try:
        from browser import get_manager

        page = get_manager().page()
        if page is None:
            return None
        url = page.url
        return url if url and not url.startswith("about:") else None
    except Exception:
        return None


def _texts_from_context(ctx) -> list[str]:
    texts: list[str] = []
    prompt = getattr(ctx, "prompt", None)
    if isinstance(prompt, str):
        texts.append(prompt)
    for message in getattr(ctx, "messages", None) or []:
        for part in getattr(message, "parts", None) or []:
            content = getattr(part, "content", None)
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        texts.append(item)
                    elif hasattr(item, "content") and isinstance(getattr(item, "content", None), str):
                        texts.append(item.content)
    return texts


def _target_url_from_prompt(ctx) -> str | None:
    for text in _texts_from_context(ctx):
        match = _URL_RE.search(text)
        if match:
            return match.group(0)
    return None


def _same_domain(a: str, b: str) -> bool:
    def normalize(url: str) -> str:
        host = urlparse(url).hostname or ""
        return host.lower().removeprefix("www.")

    return bool(normalize(a)) and normalize(a) == normalize(b)


def _is_document_discovery(ctx) -> bool:
    texts = _texts_from_context(ctx)
    blob = " ".join(texts).lower()
    if any(keyword in blob for keyword in _INTERACTION_KEYWORDS):
        return False
    hits = sum(1 for keyword in _DOC_KEYWORDS if keyword in blob)
    if hits >= 2:
        return True
    url = _current_page_url()
    if url:
        path = urlparse(url).path.lower()
        if any(signal in path for signal in _URL_PATH_SIGNALS):
            return True
    return False


async def _page_has_filter_components() -> bool:
    """True when the current page exposes an interactive filtering UI.

    Multi-signal union: table roots (generic selectors + filter_probes
    FRAMEWORK_PROBES root markers) OR component-library widget containers
    (filter_probes.FILTER_WIDGET_SELECTORS) OR custom filter inputs
    (placeholder "filter"/"筛选", contenteditable). This recognises
    component-library filter UIs (TDesign/AntD date pickers, dropdowns,
    popovers) that have no native ``<select>``. Cached per URL with a short TTL
    so SPA route/popover changes invalidate it.
    """
    url = _current_page_url()
    if url:
        entry = _page_filter_cache.get(url)
        if entry and (time.monotonic() - entry[0]) < _PAGE_FILTER_TTL:
            return entry[1]
    try:
        from browser import get_manager

        page = get_manager().page()
        if page is None:
            return False
        from tools.browser_tools.filter_probes import (
            FILTER_WIDGET_SELECTORS,
            FRAMEWORK_PROBES,
        )

        table_selectors = 'table, [role="table"], [role="grid"]' + "".join(
            f', {p["root_marker"]}' for p in FRAMEWORK_PROBES
        )
        widget_selectors = ", ".join(FILTER_WIDGET_SELECTORS)
        has = await page.evaluate(
            """(sel) => {
                const hasTable = !!document.querySelector(sel.tables);
                const hasWidget = !!document.querySelector(sel.widgets);
                const hasFilterInput = !!document.querySelector(
                    'input[placeholder*="filter" i], input[placeholder*="筛选" i], '
                    + "[contenteditable=''], [contenteditable='true']");
                const hasFilterSelect = [...document.querySelectorAll('select')]
                    .some(s => s.options.length > 1);
                return (hasTable && (hasFilterInput || hasFilterSelect || hasWidget))
                    || (hasWidget && hasFilterInput);
            }""",
            {"tables": table_selectors, "widgets": widget_selectors},
        )
    except Exception:
        return False
    if url:
        _page_filter_cache[url] = (time.monotonic(), bool(has))
    return bool(has)
