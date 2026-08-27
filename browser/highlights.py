from __future__ import annotations

import asyncio
from playwright.async_api import Page

from core.logging_setup import get_logger

logger = get_logger("browser.highlights")

HIGHLIGHT_CSS = """
#__scdb_highlight_click {
    position: fixed; inset: 0; pointer-events: none; z-index: 2147483647;
    border: 3px solid rgba(255, 59, 48, 0.85);
    border-radius: 6px;
    animation: __scdb_flash 0.6s ease-out;
}
@keyframes __scdb_flash {
    0%   { opacity: 1; }
    100% { opacity: 0; }
}
.__scdb_highlight_input {
    border: 2px solid rgba(0, 122, 255, 0.9) !important;
    box-shadow: 0 0 8px rgba(0, 122, 255, 0.5) !important;
    transition: box-shadow 0.3s ease;
}
#__scdb_scroll_indicator {
    position: fixed; bottom: 8px; right: 12px; z-index: 2147483647;
    background: rgba(0,0,0,0.7); color: #fff; font: 11px monospace;
    padding: 3px 8px; border-radius: 4px;
    pointer-events: none;
}
"""


async def inject_highlight_runtime(page: Page) -> None:
    # 高亮注入是纯装饰性的 best-effort 操作：页面导航中/上下文销毁时
    # evaluate 会抛 "Execution context was destroyed" 等异常，必须吞掉，
    # 否则会终止整个 run。
    try:
        await page.evaluate(f"""
        if (!window.__scdb_hl_ready) {{
            const style = document.createElement('style');
            style.id = '__scdb_hl_styles';
            style.textContent = `{HIGHLIGHT_CSS}`;
            document.head.appendChild(style);
            window.__scdb_hl_ready = true;
        }}
        """)
    except Exception as e:
        logger.warning(f"highlight runtime injection skipped error={e}")


async def highlight_click(page: Page, selector: str, duration_ms: int = 600) -> None:
    await inject_highlight_runtime(page)
    try:
        await page.evaluate(
            """(selector) => {
                const el = document.querySelector(selector);
                if (!el) return;
                const rect = el.getBoundingClientRect();
                const ov = document.createElement('div');
                ov.id = '__scdb_highlight_click';
                ov.style.left = rect.left + 'px';
                ov.style.top = rect.top + 'px';
                ov.style.width = rect.width + 'px';
                ov.style.height = rect.height + 'px';
                document.body.appendChild(ov);
            }""",
            selector,
        )
    except Exception as e:
        logger.warning(f"highlight_click skipped selector={selector} error={e}")
        return
    await asyncio.sleep(duration_ms / 1000)
    await page.evaluate("""
        const el = document.getElementById('__scdb_highlight_click');
        if (el) el.remove();
    """)


async def highlight_input(page: Page, selector: str) -> None:
    await inject_highlight_runtime(page)
    try:
        await page.evaluate(
            """(selector) => {
                const el = document.querySelector(selector);
                if (!el) return;
                el.classList.add('__scdb_highlight_input');
            }""",
            selector,
        )
    except Exception as e:
        logger.warning(f"highlight_input skipped selector={selector} error={e}")


async def highlight_input_remove(page: Page) -> None:
    await page.evaluate("""
    (() => {
        document.querySelectorAll('.__scdb_highlight_input')
            .forEach((el) => el.classList.remove('__scdb_highlight_input'));
        // 兼容清理旧版改 id 残留：恢复被改写的原始 id
        const legacy = document.getElementById('__scdb_highlight_input');
        if (legacy && legacy.hasAttribute('data-scdb-orig-id')) {
            legacy.id = legacy.getAttribute('data-scdb-orig-id') || '';
            legacy.removeAttribute('data-scdb-orig-id');
        }
    })();
    """)


async def highlight_scroll(page: Page, pixels: int) -> None:
    await inject_highlight_runtime(page)
    await page.evaluate(f"""
    (() => {{
        let el = document.getElementById('__scdb_scroll_indicator');
        if (!el) {{
            el = document.createElement('div');
            el.id = '__scdb_scroll_indicator';
            document.body.appendChild(el);
        }}
        const _pixels = {pixels};
        const pct = Math.round((window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100);
        el.textContent = `scroll ${{_pixels > 0 ? '\\u2193' : '\\u2191'}} ${{pct}}%`;
    }})();
    """)
    await asyncio.sleep(2)
    await page.evaluate("""
        const el = document.getElementById('__scdb_scroll_indicator');
        if (el) el.remove();
    """)
