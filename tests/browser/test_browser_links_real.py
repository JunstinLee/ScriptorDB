from __future__ import annotations

from urllib.parse import quote

import pytest

from tests.support.ctx import make_ctx

pytestmark = [
    pytest.mark.slow,
    pytest.mark.usefixtures("cleanup_browser"),
]


@pytest.mark.slow
class TestBrowserLinksReal:
    @pytest.mark.asyncio
    async def test_extract_links_and_tabs(self):
        from tools.browser import (
            browser_extract_links,
            browser_get_tabs,
            browser_launch,
            browser_navigate,
            browser_switch_tab,
        )

        result = await browser_launch(make_ctx())
        assert "launched successfully" in result.lower()

        html = (
            "<html><body>"
            "<a href='https://example.com/a'>A</a>"
            "<a href='https://example.com/b' target='_blank'>B</a>"
            "</body></html>"
        )
        result = await browser_navigate(make_ctx(), "data:text/html," + quote(html))
        assert "navigated to" in result.lower()

        result = await browser_extract_links(make_ctx())
        assert result["total"] == 2

        result = await browser_get_tabs(make_ctx())
        assert "ACTIVE" in result

        result = await browser_switch_tab(make_ctx(), 0)
        assert "Switched to tab 0" in result
