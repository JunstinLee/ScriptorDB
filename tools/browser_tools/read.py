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
    form: bool = False,
) -> str | ToolResult:
    """Read from the current page. Read-only: this tool does not change the page.

    Entry precedence when several are given: `js` > `form` > `selector` > no-arg.

    - With no `selector`, no `js` and no `form`: returns the whole page text
      (`# title` + body text).
    - With `selector`: returns the text of the matching element. `selector` accepts both
      CSS and Playwright engine selectors (`#id`, `.class`, `text=导出`,
      `li:has-text("导出全部")`, `role=button[name="导出"]`). Pass `attribute` (e.g. `href`,
      `value`) to read an attribute instead of text, and `all=True` to return every match.
    - With `js`: evaluates the snippet and returns the JSON-encoded result. Reserved for
      native state the standard tools cannot reach (pure computation, canvas pixels,
      localStorage, navigator); do not use it to probe page structure — use
      `browser_find` / `form=True` instead.
    - With `form=True`: returns one line per visible form control
      (`label -> selector (type, value=…)`, with `<select>` options), ready to pass back
      to `browser_fill` / `browser_click`. Use this instead of writing a JS snippet to
      enumerate form fields.
    """
    if (js or "").strip():
        return await _read_js(ctx, js)
    if form:
        return await _read_form(ctx)
    if (selector or "").strip():
        return await _read_selector(ctx, selector, attribute, all)
    return await _read_page_text(ctx)


async def _read_page_text(ctx) -> str:
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    from runtime.tool_middleware import (
        STATE,
        _content_revision,
        _nav_revision,
        _page_key,
        _run_key,
    )

    run_key = _run_key(ctx)
    page_key = _page_key(manager)
    nav_rev = _nav_revision(manager)
    content_rev = _content_revision(manager)
    if run_key and page_key:
        prev = STATE.get_page_read(run_key)
        if prev and prev[:3] == (page_key, nav_rev, content_rev):
            return (
                f"Page unchanged since your last full read ({prev[3]} chars); reuse it, "
                "or pass a `selector` / `js` / `form=True`."
            )

    title = await page.title()
    text = await page.inner_text("body")
    result = f"# {title}\n\n{text}"
    if run_key and page_key:
        STATE.set_page_read(run_key, (page_key, nav_rev, content_rev, len(result)))
    manager.record_action("get_text", f"Retrieved {len(result)} chars")
    return result


async def _read_form(ctx) -> str | ToolResult:
    from browser.form_scan import extract_form_js

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    try:
        controls = await page.evaluate(extract_form_js())
    except Exception as e:
        manager.record_action("read_form", f"error: {e}", success=False)
        return ToolResult(
            success=False,
            error=ToolErrorInfo(category="internal_error", message=f"Form read failed: {e}"),
        )
    visible = [c for c in controls or [] if isinstance(c, dict) and c.get("visible")]
    manager.record_action("read_form", f"{len(visible)} controls")
    if not visible:
        return "No visible form controls on the current page."
    return "\n".join(_format_control_line(c) for c in visible)


def _format_control_line(control: dict) -> str:
    label = (control.get("label") or control.get("placeholder")
             or control.get("name") or control.get("id") or "").strip()
    tag = control.get("tag") or ""
    ctype = control.get("type") or ""
    detail = tag + (f"[{ctype}]" if tag == "input" and ctype else "")
    if control.get("checked") is not None:
        detail += f" checked={control.get('checked')}"
    elif control.get("value"):
        detail += f" value={control.get('value')!r}"
    line = f"- {label!r} -> {control.get('selector')} ({detail})"
    options = control.get("options")
    if options:
        opts = ", ".join(
            repr(str(o.get("value"))) for o in options if isinstance(o, dict)
        )
        line += f" options=[{opts}]"
    return line


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
