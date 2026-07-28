from __future__ import annotations

import asyncio
from playwright.async_api import Page

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
#__scdb_highlight_input {
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
    await page.evaluate(f"""
    if (!window.__scdb_hl_ready) {{
        const style = document.createElement('style');
        style.id = '__scdb_hl_styles';
        style.textContent = `{HIGHLIGHT_CSS}`;
        document.head.appendChild(style);
        window.__scdb_hl_ready = true;
    }}
    """)


async def highlight_click(page: Page, selector: str, duration_ms: int = 600) -> None:
    await inject_highlight_runtime(page)
    await page.evaluate(f"""
    (() => {{
        const el = document.querySelector('{selector}');
        if (!el) return;
        const rect = el.getBoundingClientRect();
        const ov = document.createElement('div');
        ov.id = '__scdb_highlight_click';
        ov.style.left = rect.left + 'px';
        ov.style.top = rect.top + 'px';
        ov.style.width = rect.width + 'px';
        ov.style.height = rect.height + 'px';
        document.body.appendChild(ov);
    }})();
    """)
    await asyncio.sleep(duration_ms / 1000)
    await page.evaluate("""
        const el = document.getElementById('__scdb_highlight_click');
        if (el) el.remove();
    """)


async def highlight_input(page: Page, selector: str) -> None:
    await inject_highlight_runtime(page)
    await page.evaluate(f"""
    (() => {{
        const el = document.querySelector('{selector}');
        if (!el) return;
        el.setAttribute('data-scdb-orig-id', el.id);
        el.id = '__scdb_highlight_input';
    }})();
    """)


async def highlight_input_remove(page: Page) -> None:
    await page.evaluate("""
    (() => {
        const el = document.getElementById('__scdb_highlight_input');
        if (el) {
            el.id = el.getAttribute('data-scdb-orig-id') || '';
            el.removeAttribute('data-scdb-orig-id');
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
        const pct = Math.round((window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100);
        el.textContent = `scroll {pixels > 0 ? '\\u2193' : '\\u2191'} ${{pct}}%`;
    }})();
    """)
    await asyncio.sleep(2)
    await page.evaluate("""
        const el = document.getElementById('__scdb_scroll_indicator');
        if (el) el.remove();
    """)
