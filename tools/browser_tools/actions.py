from __future__ import annotations

import asyncio
import time

from browser.refs import invalidate_ref, resolve_ref
from config.settings import Settings
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from schemas import ToolErrorInfo, ToolResult
from tools.browser_common import (
    _check_blocked,
    _click_may_download,
    _ensure_downloads_dir,
    _read_control_value,
    _require_browser,
    _settle_after_click,
    _wait_for_download,
)
from tools.browser_tools.selectors import (
    _ACTION_TIMEOUT_MS,
    _is_engine_selector,
    _normalize_selector,
)
from tools.tool_decorators import db_tool

logger = get_logger(__name__)

_REF_RESOLVE_TIMEOUT_MS = 1500

# browser_click 的下载等待默认秒数。等于该值时走「按需判断」（见 _click_may_download）；
# 显式传其它正值则强制等待，0 跳过等待。
_DEFAULT_DOWNLOAD_WAIT = 2

# browser_fill_form 单次调用允许的最大字段数（与典型表单列数量级一致）。超限直接失败，
# 不静默截断——静默丢字段会造成数据错误。
_MAX_FILL_FORM_FIELDS = 10

_REASON_UNKNOWN = "unknown"
_REASON_PAGE_CLOSED = "page_closed"
_REASON_URL_CHANGED = "url_changed"
_REASON_ELEMENT_MISSING = "element_missing"
_REASON_SIGNATURE_MISMATCH = "signature_mismatch"

# 不保身份的定位器种类：它们本就可能解析回别的节点，硬身份冲突不能据此判 stale。
_WEAK_LOCATOR_KINDS = {"text", "path"}

# 唯一性强的定位符种类：冲突时先重采样签名、再按「选择器仍唯一可解析」放行，
# 不直接判 stale（动态重渲染页面里角色/属性抖动会误伤）。
_STRONG_UNIQUE_LOCATOR_KINDS = {"id", "data"}

# 强唯一定位符冲突时重采样签名的窗口：tries 次、每次间隔 delay 秒，取出现次数最多者。
_SIGNATURE_RESAMPLE_TRIES = 3
_SIGNATURE_RESAMPLE_DELAY = 0.05


def _click_error_category(message: str) -> str:
    low = message.lower()
    if "not found" in low:
        return "resource_not_found"
    if "not visible" in low or "is disabled" in low or "not actionable" in low:
        return "not_actionable"
    # 遮挡要先于超时判定：被别的元素挡住时 page.click 也抛 PlaywrightTimeoutError，
    # 文案里同时含 "timed out" 与 "covered"，先匹配超时会把遮挡误报成超时。
    if "covered" in low or "intercepts pointer events" in low:
        return "element_covered"
    if "timed out" in low or "timeout" in low:
        return "execution_timeout"
    return "internal_error"


def _format_click_target(target: dict) -> str:
    tag = target.get("tag") or ""
    role = target.get("role") or tag
    text = (target.get("text") or target.get("ariaLabel") or "").strip()
    value = (target.get("value") or "").strip()
    label = f" {text[:40]!r}" if text else ""
    val = f" value={value[:40]!r}" if value else ""
    return f"Target: <{tag}> [{role}]{label}{val}"


def _stale_ref(ref: str, reason: str = "") -> ToolResult:
    logger.info("ref stale: %s (%s)", ref, reason or _REASON_UNKNOWN)
    detail = f" ({reason})" if reason else ""
    return ToolResult(
        success=False,
        error=ToolErrorInfo(
            category="stale_ref",
            message=(
                f"Ref '{ref}' is stale{detail}. The page or element changed since the "
                "ref was minted. Call browser_find again to get a fresh ref."
            ),
        ),
    )


def _split_signature(sig: str) -> tuple[str, str]:
    """把 ``[tag, role, aria, text]`` 签名拆成 (结构身份, 可变信号)。

    结构身份只取 tag：标签名由标记本身决定，最稳定。role 会被状态切换/渲染
    改写（例如同一节点在 clickable/render 之间切换 role），aria-label 与
    textContent 在 SPA 里每轮渲染都可能被改写，放进结构身份都会把「同一个
    元素」误判成 stale，故一律降级为可变信号。段数不等于 4 视为不可判，
    返回 ``("", "")``，由调用方按「算不出」处理。
    """
    parts = (sig or "").split("\u0001")
    if len(parts) != 4:
        return "", ""
    return parts[0], "\u0001".join(parts[1:])


async def _element_signature(handle) -> str | None:
    from browser.locate_script import ELEMENT_SIGNATURE_JS

    try:
        return str(await handle.evaluate(ELEMENT_SIGNATURE_JS))
    except Exception:
        return None


async def _resample_signature(handle) -> str | None:
    """短窗口内多次取签名，取出现次数最多者（动态重渲染下单次采样会抖动）。"""
    samples: list[str] = []
    for _ in range(_SIGNATURE_RESAMPLE_TRIES):
        sig = await _element_signature(handle)
        if sig:
            samples.append(sig)
        await asyncio.sleep(_SIGNATURE_RESAMPLE_DELAY)
    if not samples:
        return None
    return max(set(samples), key=samples.count)


async def _selector_unique(page, selector: str) -> bool:
    """选择器是否仍唯一可解析（强唯一定位符按此判定元素未变）。"""
    try:
        return len(await page.query_selector_all(selector)) == 1
    except Exception:
        return False


async def _resolve_ref_target(manager, ref: str):
    """把 ref 解析回 (page, locator)，并证明它仍指向同一元素。

    先比对铸造时 URL（点击触发的整页跳转不经失效挂点，Page 对象跨导航不变，
    只比签名会让同 locator 同签名的元素被静默误命中），再等元素挂载后分级比对
    签名（硬身份只取 tag）：硬身份一致即命中；软信号抖动、签名算不出都记
    ``unverified`` 放行；硬身份冲突时——弱定位器失效后放行；强唯一定位符
    （id / data）先重采样签名，仍冲突且选择器已不唯一才 ``stale_ref``。
    """
    record = resolve_ref(ref)
    if record is None:
        return _stale_ref(ref, _REASON_UNKNOWN)
    page = record.page
    if page is None or page.is_closed():
        return _stale_ref(ref, _REASON_PAGE_CLOSED)
    if (page.url or "") != record.page_url:
        return _stale_ref(ref, _REASON_URL_CHANGED)
    try:
        await page.wait_for_selector(record.locator, timeout=_REF_RESOLVE_TIMEOUT_MS)
    except Exception:
        return _stale_ref(ref, _REASON_ELEMENT_MISSING)
    try:
        handle = await page.query_selector(record.locator)
    except Exception:
        handle = None
    if handle is None:
        return _stale_ref(ref, _REASON_ELEMENT_MISSING)
    signature = await _element_signature(handle)
    if signature is None:
        logger.info("ref reuse unverified: %s (signature unavailable)", ref)
        return page, record.locator
    hard, soft = _split_signature(signature)
    rec_hard, rec_soft = _split_signature(record.signature)
    if not hard or not rec_hard:
        logger.info("ref reuse unverified: %s (signature unavailable)", ref)
        return page, record.locator
    if hard == rec_hard:
        if soft != rec_soft:
            logger.info("ref reuse unverified: %s (soft text drift)", ref)
        return page, record.locator
    if record.locator_kind in _WEAK_LOCATOR_KINDS:
        logger.info(
            "ref reuse unverified: %s (weak locator %s)", ref, record.locator_kind
        )
        invalidate_ref(ref)
        return page, record.locator
    if record.locator_kind in _STRONG_UNIQUE_LOCATOR_KINDS:
        # 唯一性强：先短窗口重采样，取到稳定签名后再比一次硬身份。
        stable = await _resample_signature(handle)
        if stable is not None:
            resampled_hard, _ = _split_signature(stable)
            if resampled_hard and resampled_hard == rec_hard:
                logger.info(
                    "ref reuse unverified: %s (strong locator %s, resampled match)",
                    ref, record.locator_kind,
                )
                return page, record.locator
        # 仍冲突但选择器唯一可解析：按「定位符保身份」放行。
        if await _selector_unique(page, record.locator):
            logger.info(
                "ref reuse unverified: %s (strong locator %s, selector still unique)",
                ref, record.locator_kind,
            )
            return page, record.locator
    return _stale_ref(ref, _REASON_SIGNATURE_MISMATCH)


@db_tool(name="browser_wait_for_selector", category="browser", timeout=15, sequential=True)
async def browser_wait_for_selector(
    ctx: RunContext[Settings],
    selector: str,
    state: str = "attached",
) -> str:
    """Wait for `selector` to reach `state` (attached/detached/visible/hidden).

    `selector` accepts both CSS and Playwright engine selectors: `#id`, `.class`,
    `text=导出`, `li:has-text("导出全部")`, `role=button[name="导出"]`.
    Use `state="visible"` when you need the element to be actually shown.
    """
    from browser.context import wait_for_selector as _wait
    from browser.highlights import highlight_click

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    selector = _normalize_selector(selector)
    result = await _wait(page, selector, state)  # type: ignore[arg-type]
    if not _is_engine_selector(selector):
        await highlight_click(page, selector, block=False)
    manager.record_action("wait_for_selector", selector, selector=selector)
    return result


@db_tool(name="browser_click", category="browser", timeout=15, sequential=True)
async def browser_click(
    ctx: RunContext[Settings],
    selector: str = "",
    text: str = "",
    ref: str = "",
    download_wait: int = _DEFAULT_DOWNLOAD_WAIT,
) -> str | ToolResult:
    """Click the first element matching `selector` (or the element a `ref` points to).

    Prefer `ref` when you have one: pass the `ref` from `browser_find` and this tool
    locates the element directly without re-scanning the page. A ref is only valid
    while the page URL is unchanged; if it returns a `stale_ref` error the page has
    navigated — call `browser_find` again for a fresh ref (do not retry the old one).

    Otherwise `selector` accepts both CSS and Playwright engine selectors: `#id`,
    `.class`, `text=导出`, `li:has-text("导出全部")`, `role=button[name="导出"]`.
    As a shortcut, pass `text="导出全部"` instead of a selector to click by text.
    If the click triggers a download, this waits up to `download_wait` seconds for the
    file to be saved to the workspace outputs dir and reports "Captured download" with
    its path when it arrives. Pass `download_wait=0` to skip the wait.
    """
    from browser.actions import click as _click
    from browser.highlights import highlight_click

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    if (ref or "").strip():
        target = await _resolve_ref_target(manager, ref.strip())
        if isinstance(target, ToolResult):
            manager.record_action("click", f"stale ref {ref}", success=False)
            return target
        page, selector = target
    else:
        if not selector and text:
            selector = f"text={text}"
        if not selector:
            return ToolResult(
                success=False,
                error=ToolErrorInfo(
                    category="invalid_selector",
                    message="browser_click needs a `selector`, `text`, or `ref`.",
                ),
            )
        selector = _normalize_selector(selector)
    _ensure_downloads_dir(manager, ctx)
    if not _is_engine_selector(selector):
        await highlight_click(page, selector, block=False)
        await manager.trace.record_pre_click(page, selector)

    clicked_at = time.time()
    click_result = await _click(page, selector, timeout=_ACTION_TIMEOUT_MS)
    click_failed = click_result.startswith("Click failed")
    if click_failed:
        from browser.runtime import locate_elements

        candidates = await locate_elements(page, scope="visible")
        target = next((el for el in candidates if el.get("selector") == selector), None)
        container_key = target.get("containerKey") if target else None
        if container_key:
            candidates = [
                el for el in candidates
                if el.get("containerKey") == container_key
                and el.get("semantic") in ("calendar-day", "calendar-navigation", "calendar-month")
            ]
        else:
            candidates = [
                el for el in candidates
                if el.get("semantic") in ("calendar-day", "calendar-navigation", "calendar-month")
            ]
        if candidates:
            click_result += "\nCurrent calendar candidates: " + "; ".join(
                f"{el.get('text') or el.get('ariaLabel') or el.get('semantic')}"
                f" [{el.get('state')}]: {el.get('selector')}"
                for el in candidates[:20]
            )
    # 失败判定只看 click 执行结果，避免页面数据（快照里的 value 文本）误触发
    # record_element_failure / detect_takeover。
    failed = "failed" in click_result.lower() or "error" in click_result.lower()

    snapshot = await _settle_after_click(page, selector, quick=click_failed)
    lines = [click_result]
    if download_wait != 0:
        # 默认值走「按需判断」：只有可能下载的点击才等；显式传其它正值则强制等待。
        if download_wait == _DEFAULT_DOWNLOAD_WAIT:
            may_download = await _click_may_download(page, selector)
        else:
            may_download = True
        entry = await _wait_for_download(
            manager, clicked_at, download_wait, may_download=may_download
        )
        if entry and entry.get("ok"):
            lines.append(f"Captured download: {entry.get('filename')} ({entry.get('path')})")
        elif entry:
            lines.append(f"Warning: a download was triggered but not saved: {entry.get('reason')}")

    target = snapshot.get("target")
    if isinstance(target, dict):
        lines.append(_format_click_target(target))
    lines.append(f"Overlay: {snapshot.get('overlays', 0)} visible panel(s)")
    fields = snapshot.get("fields") or []
    if fields:
        lines.append("Fields: " + "; ".join(
            f"placeholder={f.get('placeholder')!r} value={f.get('value')!r}"
            for f in fields if isinstance(f, dict)
        ))

    trace = await manager.trace.record_post_nav(page)
    detail = selector
    pre = trace.get("pre_click") or {}
    final_url = trace.get("final_url") or ""
    if final_url:
        lines.append(f"Page state: {final_url} ({trace.get('title') or ''})")
    if pre.get("url") and final_url and pre.get("url") != final_url:
        detail = f"{selector} -> {final_url}"
    result = "\n".join(lines)
    manager.record_action("click", detail, selector=selector,
                          success="Clicked" in result)
    if failed:
        manager.record_element_failure(selector)
        await manager.detect_takeover()
    if click_failed:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category=_click_error_category(click_result),
                message=result,
            ),
        )
    return result


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
    from browser.highlights import highlight_input, highlight_input_remove
    from browser.sensitive import current_site_password, is_password_control

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    if (ref or "").strip():
        target = await _resolve_ref_target(manager, ref.strip())
        if isinstance(target, ToolResult):
            manager.record_action("fill", f"stale ref {ref}", success=False)
            return target
        page, selector = target
    else:
        if not selector:
            return ToolResult(
                success=False,
                error=ToolErrorInfo(
                    category="invalid_selector",
                    message="browser_fill needs a `selector` or `ref`.",
                ),
            )
        selector = _normalize_selector(selector)
    pwd = current_site_password(
        page.url, ctx.deps.workspace_id if ctx.deps else None
    )
    if (
        await is_password_control(page, selector)
        and pwd is not None
        and pwd in text
    ):
        # 密码控件且内容为系统密码：系统已自动填充，跳过二次填写。
        # 不执行 record_element_failure/detect_takeover（非页面故障）。
        manager.record_action(
            "fill", "skipped (system-filled password)",
            selector=selector, success=True,
        )
        return "This password was filled automatically by the system; do not fill it again"
    from browser.actions import fill as _fill
    if not _is_engine_selector(selector):
        await highlight_input(page, selector)
    try:
        result = await _fill(page, selector, text, timeout=_ACTION_TIMEOUT_MS)
    finally:
        await highlight_input_remove(page)
    manager.record_action("fill", selector, selector=selector,
                          success="Filled" in result)
    if "not editable" not in str(result).lower() and (
        "failed" in str(result).lower() or "error" in str(result).lower()
    ):
        manager.record_element_failure(selector)
        await manager.detect_takeover()
    # 成功后在返回文本里附上写入后的 value，省掉模型再发一次回读自检。
    # 追加放在失败判定之后，避免页面数据里的 "failed"/"error" 文本污染判定。
    if "Filled" in result and not _is_engine_selector(selector):
        value_after = await _read_control_value(page, selector)
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
    """
    from browser.actions import fill as _fill
    from browser.highlights import highlight_input, highlight_input_remove
    from browser.sensitive import current_site_password, is_password_control

    selector = str(entry.get("selector") or "").strip()
    ref = str(entry.get("ref") or "").strip()
    value = str(entry.get("text") or "")
    label = selector or ref
    if ref:
        target = await _resolve_ref_target(manager, ref)
        if isinstance(target, ToolResult):
            manager.record_action("fill", f"stale ref {ref}", success=False)
            detail = target.error.message if target.error else "stale ref"
            return False, f"{label}: {detail}", page
        page, selector = target
    else:
        selector = _normalize_selector(selector)
    pwd = current_site_password(page.url, ctx.deps.workspace_id if ctx.deps else None)
    if (
        await is_password_control(page, selector)
        and pwd is not None
        and pwd in value
    ):
        manager.record_action(
            "fill", "skipped (system-filled password)",
            selector=selector, success=True,
        )
        return True, f"{label}: filled automatically by the system", page
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
    return ok, f"{label}: {result}", page


@db_tool(name="browser_fill_form", category="browser", timeout=15, sequential=True)
async def browser_fill_form(
    ctx: RunContext[Settings],
    fields: list[dict],
) -> str | ToolResult:
    """Fill multiple form fields in one call.

    `fields` is a list of entries, each shaped like a `browser_fill` call:
    `{"selector": "#name", "text": "Alice"}` (or `{"ref": "ref_1a2b3c4d", "text": "Alice"}`).
    Each entry needs a `selector` or a `ref`; the value to write goes in `text`.

    At most 10 fields per call — pass more and the call fails (split it into several
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


@db_tool(name="browser_select_option", category="browser", timeout=15, sequential=True)
async def browser_select_option(
    ctx: RunContext[Settings],
    selector: str = "",
    value: str = "",
    label: str = "",
    ref: str = "",
) -> str | ToolResult:
    """Select an option in the `<select>` matching `selector` (or the element a `ref` points to).

    Prefer `ref` when you have one: pass the `ref` from `browser_find` and the control is
    located directly without re-scanning. A ref is only valid while the page URL is
    unchanged; on a `stale_ref` error call `browser_find` again for a fresh ref.

    Pass `value` (the option's value attribute) or `label` (its visible text).
    """
    from browser.actions import select_option as _select
    from browser.highlights import highlight_input, highlight_input_remove

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    if (ref or "").strip():
        target = await _resolve_ref_target(manager, ref.strip())
        if isinstance(target, ToolResult):
            manager.record_action("select_option", f"stale ref {ref}", success=False)
            return target
        page, selector = target
    elif not selector:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="invalid_selector",
                message="browser_select_option needs a `selector` or `ref`.",
            ),
        )
    if not value and not label:
        return "browser_select_option requires a value or a label"
    if not _is_engine_selector(selector):
        await highlight_input(page, selector)
    try:
        result = await _select(page, selector, value=value, label=label, timeout=_ACTION_TIMEOUT_MS)
    finally:
        await highlight_input_remove(page)
    manager.record_action("select_option", f"{selector} = {value or label}", selector=selector,
                          success="Selected" in result)
    if "failed" in str(result).lower() or "error" in str(result).lower():
        manager.record_element_failure(selector)
        await manager.detect_takeover()
    return result


@db_tool(name="browser_press_key", category="browser", timeout=15, sequential=True)
async def browser_press_key(ctx: RunContext[Settings], key: str) -> str:
    from browser.actions import press_key as _press

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await _press(page, key)
    manager.record_action("press_key", key)
    return result


@db_tool(name="browser_scroll", category="browser", timeout=15, sequential=False, defer_loading=True)
async def browser_scroll(
    ctx: RunContext[Settings],
    to_bottom: bool = True,
    pixels: int = 0,
) -> str:
    from browser.actions import scroll_by, scroll_to_bottom
    from browser.highlights import highlight_scroll

    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked

    if to_bottom:
        result = await scroll_to_bottom(page)
        await highlight_scroll(page, 9999)
    elif pixels == 0:
        return "pixels must be non-zero when to_bottom is False"
    else:
        result = await scroll_by(page, pixels)
        await highlight_scroll(page, pixels)

    manager.record_action("scroll", "bottom" if to_bottom else f"{pixels}px")
    return result
