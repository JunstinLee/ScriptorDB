from __future__ import annotations

import asyncio
import time

from browser import get_manager
from browser.takeover import HumanTakeoverState
from core.logging_setup import get_logger

logger = get_logger("tools.browser")

_NEXT_SELECTOR_CANDIDATES = (
    '[rel="next"]',
    ".pager-next",
    ".next",
    ".pagination-next",
    'button.next',
    '[aria-label*="next" i]',
)


def _require_browser() -> tuple:
    manager = get_manager()
    manager.cancel_idle_close()
    return manager, manager.page()


def _ensure_downloads_dir(manager, ctx) -> None:
    """按当前 workspace 惰性设置下载目录，避免依赖 browser_launch 的时机。"""
    deps = getattr(ctx, "deps", None) if ctx is not None else None
    workspace_path = getattr(deps, "workspace_path", None) if deps is not None else None
    if workspace_path:
        from config.workspace import workspace_outputs_dir
        manager.set_downloads_dir(workspace_outputs_dir(workspace_path))


def _check_blocked(manager) -> str | None:
    state = manager.takeover.state
    if state in (HumanTakeoverState.HUMAN_CONTROL, HumanTakeoverState.WAITING_HUMAN, HumanTakeoverState.DETECTED):
        logger.warning(f"[BLOCKED] browser tool blocked, takeover_state={state.value}")
        return f"Browser interaction blocked: takeover state is '{state.value}'. Agent cannot control the browser until human takeover is completed or cancelled."
    return None


async def _click_next(page, selector: str) -> bool:
    """Click the site-pagination "next" button; return False if unavailable."""
    sel = selector
    if not sel:
        for candidate in _NEXT_SELECTOR_CANDIDATES:
            if await page.query_selector(candidate) is not None:
                sel = candidate
                break
        if not sel:
            return False
    element = await page.query_selector(sel)
    if element is None:
        return False
    try:
        if await element.get_attribute("disabled") is not None:
            return False
        aria = await element.get_attribute("aria-disabled")
        if aria and str(aria).lower() == "true":
            return False
        await element.click()
        return True
    except Exception:
        try:
            clicked = await page.evaluate(
                "(s) => { const b = document.querySelector(s); if (b) { b.click(); return true; } return false; }",
                sel,
            )
            return bool(clicked)
        except Exception:
            return False


_CLICK_SNAPSHOT_JS = """(selector) => {
    const laidOut = (el) => {
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return !(cs.display === "none" || cs.visibility === "hidden" ||
                 r.width <= 0 || r.height <= 0);
    };
    let target = null;
    if (selector) {
        try {
            const t = document.querySelector(selector);
            if (t) {
                target = {
                    tag: t.tagName.toLowerCase(),
                    role: t.getAttribute("role") || "",
                    text: (t.innerText || "").trim().slice(0, 60),
                    ariaLabel: t.getAttribute("aria-label") || "",
                    value: (t.value !== undefined ? String(t.value) : ""),
                };
            }
        } catch (e) { target = null; }
    }
    let overlays = 0;
    for (const o of document.querySelectorAll(
        'dialog, [role="dialog"], [role="menu"], [role="listbox"], [aria-modal="true"], ' +
        '[class*="popover"], [class*="dropdown"], [class*="picker-panel"], ' +
        '.t-popup, .t-date-picker__panel'
    )) {
        if (laidOut(o)) overlays++;
    }
    const fields = [];
    for (const el of document.querySelectorAll("input, textarea")) {
        if (!laidOut(el)) continue;
        const placeholder = el.getAttribute("placeholder") || "";
        const value = el.value || "";
        if (!placeholder && !value) continue;
        fields.push({ placeholder: placeholder, value: value });
        if (fields.length >= 8) break;
    }
    return { target: target, overlays: overlays, fields: fields };
}"""


async def _settle_after_click(page, selector: str = "", quick: bool = False) -> dict:
    """点击后等页面稳定，并返回一次轻量状态快照。

    快照含目标控件信息、当前可见覆盖层数、以及可见输入框/文本域的
    placeholder 与 value —— 让一次 click 就能判定"值有没有写进去、
    面板有没有关掉"，避免模型再用 get_text/evaluate 反复复核。
    """
    # quick=True（点击失败路径）跳过 networkidle 等待：点击自身最长 12s 超时，
    # 若再叠固定等待会撞上工具 15s 上限，反把失败变成超时。
    # 站点多为前端渲染 + 秒级刷新，networkidle 判据偏脆，容易吃满超时，
    # 故把等待窗口压到 2s + 500ms，仍返回同一份快照供上层消费。
    if not quick:
        try:
            await page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            pass
        await page.wait_for_timeout(500)
    try:
        snapshot = await page.evaluate(_CLICK_SNAPSHOT_JS, selector or "")
    except Exception:
        return {}
    return snapshot if isinstance(snapshot, dict) else {}


_CLICK_MAY_DOWNLOAD_JS = """(selector) => {
    const hit = (text) => {
        const low = String(text || '').toLowerCase();
        return ['下载', '导出', 'download', 'export'].some((h) => low.includes(h));
    };
    try {
        const el = document.querySelector(selector);
        if (!el) return false;
        if (el.hasAttribute && el.hasAttribute('download')) return true;
        const href = (el.getAttribute && (el.getAttribute('href') || '')) || '';
        if (href && /\\.(csv|xls|xlsx|pdf|zip|doc|docx|ppt|pptx|txt)([?#]|$)/i.test(href)) {
            return true;
        }
        const text = (el.innerText || el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '');
        return hit(text);
    } catch (e) {
        return true;
    }
}"""


_READ_VALUE_JS = """(selector) => {
    try {
        const el = document.querySelector(selector);
        if (!el) return null;
        return (el.value !== undefined ? String(el.value) : '');
    } catch (e) {
        return null;
    }
}"""


async def _read_control_value(page, selector: str) -> str | None:
    """读取控件写入后的 value；读不到（选择器非法 / 元素缺失）返回 None。"""
    try:
        value = await page.evaluate(_READ_VALUE_JS, selector)
    except Exception:
        return None
    return value if isinstance(value, str) else None


async def _click_may_download(page, selector: str) -> bool:
    """判断这次点击是否可能触发下载（带 download 属性 / 文件链接 / 下载类文案）。

    拿不准（选择器不是合法 CSS、脚本抛错）时返回 True —— 宁可多等一次也不漏下载。
    """
    try:
        return bool(await page.evaluate(_CLICK_MAY_DOWNLOAD_JS, selector))
    except Exception:
        return True


async def _wait_for_download(
    manager, since: float, timeout: float = 2.0, may_download: bool = True
) -> dict | None:
    """Wait for a new download record (ts >= since) to appear, up to ``timeout`` seconds.

    Polls ``manager.recent_downloads`` so a download that arrives later than the click
    is still confirmed instead of being missed. Returns the newest record (``ok`` True or
    False), or ``None`` if nothing arrives before the timeout.

    ``may_download=False`` 时确定不会有下载，直接返回 ``None``（跳过轮询）。
    """
    if not may_download:
        return None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entries = manager.recent_downloads(since)
        if entries:
            return entries[-1]
        await asyncio.sleep(0.5)
    return None
