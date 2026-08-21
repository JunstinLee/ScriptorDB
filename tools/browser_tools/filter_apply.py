from __future__ import annotations

import json
import re

from config.settings import Settings
from core.logging_setup import get_logger
from pydantic_ai import RunContext
from tools.browser_common import _check_blocked, _require_browser, _settle_after_click
from tools.browser_tools.filter_contract import FILTER_ACTIONS, is_filter_failure
from tools.tool_decorators import db_tool
from tools.validators import validate_filter_apply_args

logger = get_logger("tools.browser.filters")
_SUBMIT_LABEL_RE = "apply|search|filter|query|go|运行|应用|筛选|查询|搜索|确定"


async def _resolve(page, target: str):
    """按 name 定位：label/aria → placeholder → 按钮文本 → CSS 兜底。"""
    t = target.strip()
    for loc in (page.get_by_label(t, exact=True),
                page.get_by_placeholder(t, exact=True),
                page.get_by_role("button", name=re.compile(re.escape(t), re.IGNORECASE)).first):
        if await loc.count() > 0:
            return loc
    return page.locator(t)


async def _do_select(loc, target: str, value: str) -> str:
    opts = await loc.evaluate(
        "el => Array.from(el.options).map(o => ({ v: o.value, t: o.textContent.trim() }))"
    ) or []
    vals, texts = [o["v"] for o in opts], [o["t"] for o in opts]
    try:
        if value in vals:
            await loc.select_option(value=value)
        elif value in texts:
            await loc.select_option(label=value)
        else:
            return f"失败: select '{target}' 无匹配选项 '{value}'（可选: {texts[:10]}）"
    except Exception as e:
        return f"失败: 设置 select '{target}' 出错: {e}"
    return f"已设置 {target} = {value}"


async def _do_input(page, loc, target: str, value: str) -> str:
    try:
        await loc.fill(value)
        await page.keyboard.press("Enter")
    except Exception as e:
        return f"失败: 填写 '{target}' 出错: {e}"
    return f"已填写 {target} = {value}"


async def _do_toggle(loc, target: str, value: str) -> str:
    try:
        checked = await loc.is_checked()
    except Exception:
        return f"失败: 元素不可操作（非 checkbox/radio）: {target}"
    want = str(value).lower() in ("true", "1", "on", "checked", "yes")
    try:
        if checked != want:
            await (loc.check() if want else loc.uncheck())
    except Exception as e:
        return f"失败: 切换 '{target}' 出错: {e}"
    return f"已{'勾选' if want else '取消勾选'} {target}"


async def _do_range(loc, target: str, value: str) -> str:
    ok = await loc.evaluate(
        """(el, args) => { el.value = args.value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true; }""",
        {"value": value},
    )
    return f"已设置滑块 {target} = {value}" if ok else f"失败: 元素不可操作（非滑块）: {target}"


async def _do_dates(page, loc, target: str, values_raw: str) -> str:
    try:
        values = json.loads(values_raw)
    except json.JSONDecodeError:
        return "失败: values 不是合法 JSON"
    if not isinstance(values, list) or len(values) != 2:
        return "失败: date_range 需要 values 提供两个值（JSON 数组）"
    second = await loc.evaluate(
        """(el) => {
            const sibs = Array.from(el.parentElement.querySelectorAll('input[type="date"], input[type="datetime-local"]'));
            const n = sibs[sibs.indexOf(el) + 1];
            if (!n) return null;
            if (n.id) return '#' + CSS.escape(n.id);
            const nm = n.getAttribute('name');
            return nm ? 'input[name="' + CSS.escape(nm) + '"]' : null;
        }"""
    )
    try:
        await loc.fill(str(values[0]))
        if second:
            await page.locator(second).fill(str(values[1]))
    except Exception as e:
        return f"失败: 填写日期区间出错: {e}"
    return f"已设置 {target} = {values[0]} ~ {values[1]}"


async def _click_submit(page, loc) -> str:
    btn_re = re.compile(_SUBMIT_LABEL_RE, re.IGNORECASE)
    try:
        form = loc.locator("xpath=ancestor::form[1]")
        if await form.count() > 0:
            btn = form.get_by_role("button", name=btn_re).first
            if await btn.count() > 0:
                await btn.click()
                return "已点击提交按钮"
        btn = page.get_by_role("button", name=btn_re).first
        if await btn.count() > 0:
            await btn.click()
            return "已点击提交按钮"
    except Exception as e:
        return f"提示: 提交按钮点击失败（筛选可能已即时生效）: {e}"
    return ""


async def execute_filter_action(page, action: str, target: str, value: str = "",
                                values: str = "", submit: bool = True) -> str:
    """执行单个筛选动作并等待结果稳定（browser_apply_filter 与面板直连共用）。失败以"失败:"开头。"""
    try:
        loc = await _resolve(page, target)
    except Exception as e:
        return f"失败: 定位筛选器 '{target}' 出错: {e}"
    if await loc.count() == 0:
        return f"失败: 未找到筛选器 '{target}'"
    lines = []
    try:
        if action == "select":
            lines.append(await _do_select(loc, target, value))
        elif action == "input":
            lines.append(await _do_input(page, loc, target, value))
        elif action == "toggle":
            lines.append(await _do_toggle(loc, target, value))
        elif action == "set_range":
            lines.append(await _do_range(loc, target, value))
        elif action == "date_range":
            lines.append(await _do_dates(page, loc, target, values))
        else:
            return f"失败: 未知动作 {action}（可选: {FILTER_ACTIONS}）"
        if submit:
            lines.append(await _click_submit(page, loc))
            await _settle_after_click(page)
    except Exception as e:
        return f"失败: 执行筛选动作出错: {e}"
    return "\n".join(line for line in lines if line)


@db_tool(name="browser_apply_filter", category="browser", timeout=30, sequential=True,
         requires_approval=True, validator=validate_filter_apply_args)
async def browser_apply_filter(ctx: RunContext[Settings], action: str, target: str,
                               value: str = "", values: str = "", submit: bool = True) -> str:
    """在浏览器页面执行筛选动作（需用户确认后生效）。target 为 detect 返回的筛选器 name；date_range 用 values 提供起止值。"""
    manager, page = _require_browser()
    if page is None:
        return "Browser not launched. Please call browser_launch first."
    if blocked := _check_blocked(manager):
        return blocked
    result = await execute_filter_action(page, action, target, value, values, submit)
    failed = is_filter_failure(result)
    manager.record_action("apply_filter", result.replace("\n", " | ")[:200], selector=target,
                          success=not failed)
    if failed:
        manager.record_element_failure(target)
        await manager.detect_takeover()
    return result
