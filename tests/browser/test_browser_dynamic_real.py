from __future__ import annotations

import pytest

from tests.support.ctx import make_ctx

pytestmark = [
    pytest.mark.slow,
    pytest.mark.usefixtures("cleanup_browser"),
]


class TestBrowserDynamicRender:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_apple_dynamic_render(self):
        from tools.browser import (
            browser_evaluate,
            browser_get_text,
            browser_launch,
            browser_load_state,
            browser_navigate,
            browser_query,
            browser_screenshot,
            browser_scroll,
        )

        result = await browser_launch(make_ctx())
        assert "launched successfully" in result.lower()

        result = await browser_navigate(make_ctx(), "https://www.apple.com")
        assert "navigated to" in result.lower()

        result = await browser_load_state(make_ctx(), "networkidle")
        assert "reached load state" in result.lower()

        result = await browser_evaluate(make_ctx(), "document.title")
        assert "Apple" in result

        result = await browser_query(make_ctx(), "h1")
        assert len(result) > 0

        result = await browser_query(make_ctx(), "img[src]", attribute="src", all=True)
        assert len(result) > 0

        result = await browser_scroll(make_ctx(), to_bottom=True)
        assert "bottom" in result.lower()

        result = await browser_screenshot(make_ctx(), "outputs/browser/apple_test.png")
        assert "Screenshot saved to" in result
