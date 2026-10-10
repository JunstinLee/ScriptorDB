"""填写类工具：browser_fill / browser_fill_form。

两者共用同一填充原语 :func:`_fill_control`（ref 解析 → 系统密码跳过 → 高亮 →
填入 → 副作用记账），差异只在结果到展示文本的映射。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from browser.ref_verify import _resolve_ref_target
from config.settings import Settings
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from schemas import ToolErrorInfo, ToolResult
from tools.browser_common import _check_blocked, _read_control_value, _require_browser
from tools.browser_tools.selectors import (
    _ACTION_TIMEOUT_MS,
    _is_engine_selector,
    _normalize_selector,
)
from tools.tool_decorators import db_tool

logger = get_logger("tools.browser.fill")

# browser_fill_form 单次调用允许的最大字段数（与典型表单列数量级一致）。超限直接失败，
# 不静默截断——静默丢字段会造成数据错误。
_MAX_FILL_FORM_FIELDS = 12


@dataclass
class _FillOutcome:
    """一次填充的结果。``status`` ∈ filled / skipped_password / stale_ref / failed。"""

    page: Any
    selector: str
    status: str
    message: str


async def _fill_control(
    manager,
    ctx,
    page,
    *,
    selector: str = "",
    ref: str = "",
    value: str = "",
) -> _FillOutcome:
    """填充单一字段的共用原语（browser_fill 与 browser_fill_form 复用）。

    ref 命中时返回 ref 铸造时的 page；系统已代填的密码控件跳过二次填写。
    """
    from browser.actions import fill as _fill
    from browser.highlights import highlight_input, highlight_input_remove
    from browser.sensitive import current_site_password, is_password_control

    if ref:
        target = await _resolve_ref_target(manager, ref)
        if isinstance(target, ToolResult):
            manager.record_action("fill", f"stale ref {ref}", success=False)
            detail = target.error.message if target.error else "stale ref"
            return _FillOutcome(page, ref, "stale_ref", detail)
        page, selector = target
    else:
        selector = _normalize_selector(selector)
    pwd = current_site_password(page.url, ctx.deps.workspace_id if ctx.deps else None)
    if await is_password_control(page, selector) and pwd is not None and pwd in value:
        # 密码控件且内容为系统密码：系统已自动填充，跳过二次填写。
        # 不执行 record_element_failure/detect_takeover（非页面故障）。
        manager.record_action(
            "fill", "skipped (system-filled password)",
            selector=selector, success=True,
        )
        return _FillOutcome(page, selector, "skipped_password", "")
    if not _is_engine_selector(selector):
        await highlight_input(page, selector)
    try:
        result = await _fill(page, selector, value, timeout=_ACTION_TIMEOUT_MS)
    finally:
        await highlight_input_remove(page)
    ok = "Filled" in result
    manager.record_action("fill", selector, selector=selector, success=ok)
    if "not editable" not in str(result).lower() and (
        "failed" in str(result).lower() or "error" in str(result).lower()
    ):
        manager.record_element_failure(selector)
        await manager.detect_takeover()
    return _FillOutcome(page, selector, "filled" if ok else "failed", result)


@db_tool(name="browser_fill", category="browser", timeout=15, sequential=True)
async def browser_fill(
    ctx: RunContext[Settings],
    selector: str = "",
    text: str = "",
    ref: str = "",
) -> str | ToolResult:
    """Fill the field matching `selector` (or the element a `ref` points to) with `text`.

    Prefer `ref` when you have one: pass the `ref` from `browser_find` and the field is
    located directly without re-scanning. A ref is only valid while the page URL is
    unchanged; on a `stale_ref` error call `browser_find` again for a fresh ref.

    Otherwise `selector` accepts CSS and Playwright engine selectors (`#id`,
    `input[placeholder="…"]`, `role=textbox[name="…"]`). Filling a read-only or
    disabled field fails immediately; use the page's own widget (e.g. a date
    picker) for such fields instead.
    """
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    stripped_ref = (ref or "").strip()
    if not stripped_ref and not selector:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="invalid_selector",
                message="browser_fill needs a `selector` or `ref`.",
            ),
        )
    outcome = await _fill_control(
        manager, ctx, page, selector=selector, ref=stripped_ref, value=text
    )
    if outcome.status == "stale_ref":
        return ToolResult(
            success=False,
            error=ToolErrorInfo(category="stale_ref", message=outcome.message),
        )
    if outcome.status == "skipped_password":
        return "This password was filled automatically by the system; do not fill it again"
    result = outcome.message
    # 成功后在返回文本里附上写入后的 value，省掉模型再发一次回读自检。
    if outcome.status == "filled" and not _is_engine_selector(outcome.selector):
        value_after = await _read_control_value(outcome.page, outcome.selector)
        if value_after is not None:
            result = f"{result} (value now {value_after!r})"
    return result


async def _fill_form_error(message: str) -> ToolResult:
    return ToolResult(
        success=False,
        error=ToolErrorInfo(category="invalid_selector", message=message),
    )


def _fill_form_entry_key(entry: dict) -> str:
    """字段的身份键：selector 优先，其次 ref；都没有返回空串（视为未知字段名）。"""
    selector = str(entry.get("selector") or "").strip()
    if selector:
        return _normalize_selector(selector)
    ref = str(entry.get("ref") or "").strip()
    return f"ref:{ref}" if ref else ""


async def _fill_form_one(manager, ctx, page, entry: dict) -> tuple[bool, str, object]:
    """填写单个字段（沿用 browser_fill 的定位/高亮/副作用），返回 (ok, 展示文本, page)。

    page 会随 ref 解析结果更新（ref 命中时返回 ref 铸造时的 page）。
    带 ``label`` 的字段项按 ``<select>`` 处理：以 ``label`` 作为选项文本走
    select_option 原语。
    """
    selector = str(entry.get("selector") or "").strip()
    ref = str(entry.get("ref") or "").strip()
    value = str(entry.get("text") or "")
    option_label = str(entry.get("label") or "").strip()
    label = selector or ref
    if option_label:
        from browser.actions import select_option as _select

        if ref:
            target = await _resolve_ref_target(manager, ref)
            if isinstance(target, ToolResult):
                manager.record_action("select_option", f"stale ref {ref}", success=False)
                detail = target.error.message if target.error else "stale ref"
                return False, f"{label}: {detail}", page
            page, selector = target
        else:
            selector = _normalize_selector(selector)
        result = await _select(page, selector, label=option_label, timeout=_ACTION_TIMEOUT_MS)
        ok = "Selected" in result
        manager.record_action("select_option", f"{selector} = {option_label}",
                              selector=selector, success=ok)
        if not ok:
            manager.record_element_failure(selector)
            await manager.detect_takeover()
        return ok, f"{label}: {result}", page
    outcome = await _fill_control(
        manager, ctx, page, selector=selector, ref=ref, value=value
    )
    if outcome.status == "stale_ref":
        return False, f"{label}: {outcome.message}", outcome.page
    if outcome.status == "skipped_password":
        return True, f"{label}: filled automatically by the system", outcome.page
    detail = f"{label}: {outcome.message}"
    # 成功后在返回文本里附上写入后的 value，省掉模型再发一次回读自检（与 browser_fill 同形）。
    if outcome.status == "filled" and not _is_engine_selector(outcome.selector):
        from browser.sensitive import is_password_control
        if not await is_password_control(outcome.page, outcome.selector):
            value_after = await _read_control_value(outcome.page, outcome.selector)
            if value_after is not None:
                detail = f"{detail} (value now {value_after!r})"
    return outcome.status == "filled", detail, outcome.page


@db_tool(name="browser_fill_form", category="browser", timeout=15, sequential=True)
async def browser_fill_form(
    ctx: RunContext[Settings],
    fields: list[dict],
) -> str | ToolResult:
    """Fill multiple form fields in one call.

    `fields` is a list of entries, each shaped like a `browser_fill` call:
    `{"selector": "#name", "text": "Alice"}` (or `{"ref": "ref_<from browser_find>", "text": "Alice"}`).
    Each entry needs a `selector` or a `ref`; the value to write goes in `text`.

    For a `<select>` control, put the option's visible text in `label` instead of
    `text` — the entry is then handled with the browser_select_option primitive, so a
    dropdown is filled in the same call as the text fields:
    `{"selector": "#country", "label": "China"}`.

    At most 12 fields per call — pass more and the call fails (split it into several
    calls). Duplicate `selector`/`ref` entries and entries missing both also fail.
    Fields are filled serially; the result reports each field's outcome.
    """
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    if not isinstance(fields, list) or not fields:
        return await _fill_form_error(
            "browser_fill_form needs a non-empty `fields` list."
        )
    if len(fields) > _MAX_FILL_FORM_FIELDS:
        return await _fill_form_error(
            f"browser_fill_form accepts at most {_MAX_FILL_FORM_FIELDS} fields per call "
            f"(got {len(fields)}). Split it into multiple calls."
        )
    seen: set[str] = set()
    for index, entry in enumerate(fields):
        if not isinstance(entry, dict):
            return await _fill_form_error(
                f"browser_fill_form entry #{index} must be an object with "
                "`selector` or `ref` plus `text`."
            )
        key = _fill_form_entry_key(entry)
        if not key:
            return await _fill_form_error(
                f"browser_fill_form entry #{index} has neither `selector` nor `ref`."
            )
        if key in seen:
            return await _fill_form_error(
                f"browser_fill_form entry #{index} duplicates field {key!r}."
            )
        seen.add(key)

    lines: list[str] = []
    ok_count = 0
    for entry in fields:
        ok, detail, page = await _fill_form_one(manager, ctx, page, entry)
        if ok:
            ok_count += 1
        lines.append(f"- {detail}")
    header = f"Filled {ok_count}/{len(fields)} field(s):"
    return "\n".join([header, *lines])
