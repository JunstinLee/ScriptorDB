"""browser_read：读取页面文本 / 属性 / 原生 JS 状态（只读）。

四种入口：无参读整页文本、selector 读文本、selector+attribute 读属性、
js 执行脚本读原生状态。
"""

from __future__ import annotations

from config.settings import Settings
from pydantic_ai import RunContext
from schemas import ToolErrorInfo, ToolResult
from tools.browser_common import _check_blocked, _require_browser
from tools.browser_tools.selectors import _normalize_selector
from tools.tool_decorators import db_tool


@db_tool(name="browser_read", category="browser", timeout=15, sequential=True)
async def browser_read(
    ctx: RunContext[Settings],
    selector: str = "",
    attribute: str = "",
    all: bool = False,
    js: str = "",
) -> str | ToolResult:
    """Read from the current page. Read-only: this tool does not change the page.

    - With no `selector` and no `js`: returns the whole page text (`# title` + body text).
    - With `selector`: returns the text of the matching element. `selector` accepts both
      CSS and Playwright engine selectors (`#id`, `.class`, `text=导出`,
      `li:has-text("导出全部")`, `role=button[name="导出"]`). Pass `attribute` (e.g. `href`,
      `value`) to read an attribute instead of text, and `all=True` to return every match.
    - With `js`: evaluates the snippet and returns the JSON-encoded result. Reserved for
      native state the standard tools cannot reach (pure computation, canvas pixels,
      localStorage, navigator); do not use it to probe page structure — use
      `browser_find` / `browser_read` (selector) instead.
    """
    if (js or "").strip():
        return await _read_js(ctx, js)
    if (selector or "").strip():
        return await _read_selector(ctx, selector, attribute, all)
    return await _read_page_text(ctx)


async def _read_page_text(ctx) -> str:
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    title = await page.title()
    text = await page.inner_text("body")
    result = f"# {title}\n\n{text}"
    manager.record_action("get_text", f"Retrieved {len(result)} chars")
    return result


async def _read_selector(ctx, selector: str, attribute: str, all: bool) -> str | ToolResult:
    from browser.runtime import get_image_sources, query_attr, query_attr_all, query_text, query_text_all
    from browser.runtime import InvalidSelectorError
    from browser.sensitive import is_password_control

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    selector = _normalize_selector(selector)

    try:
        if selector == "img[src]" and attribute == "src" and all:
            result = await get_image_sources(page)
            manager.record_action("query", selector)
            return result

        if attribute:
            if attribute == "value" and await is_password_control(page, selector):
                # 密码控件（系统凭证已由 autofill 填入）：不读 DOM value，
                # 返回占位；all=True 对 selector 首元素判定一次，命中整组占位。
                result = "[redacted: password field]"
            elif all:
                result = await query_attr_all(page, selector, attribute)
            else:
                result = await query_attr(page, selector, attribute)
        elif all:
            result = await query_text_all(page, selector)
        else:
            result = await query_text(page, selector)
    except InvalidSelectorError as e:
        manager.record_action("query", selector, success=False)
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="invalid_selector",
                message=(
                    f"Invalid selector '{selector}': {e}. Use a CSS selector or a "
                    'Playwright engine selector such as li:has-text("…") or text=…'
                ),
            ),
        )

    manager.record_action("query", selector)
    return result


async def _read_js(ctx, js: str) -> str:
    from browser.runtime import evaluate as _eval
    from browser.sensitive import current_site_password
    from runtime.redact import redact

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    pwd = current_site_password(
        page.url, ctx.deps.workspace_id if ctx.deps else None
    )
    if pwd is not None and pwd in js:
        # 脚本携带系统站点密码：禁止读取或回写密码字段。
        return "Refused: the script contains the system site password; password fields must not be read or written"
    result = await _eval(page, js)
    result = redact(result)
    manager.record_action("evaluate", js[:50] + "..." if len(js) > 50 else js)
    return result
