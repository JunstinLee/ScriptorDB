from __future__ import annotations

import pytest

from tests.support.ctx import make_ctx
from tools.browser import (
    browser_get_text,
    browser_launch,
    browser_navigate,
)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.usefixtures("cleanup_browser"),
]


class TestBrowserIntegration:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_real_browser_launch_navigate_and_get_text(self):
        result = await browser_launch(make_ctx())
        assert "launched successfully" in result.lower()

        result = await browser_navigate(make_ctx(), "http://example.com")
        assert "navigated to" in result.lower()

        result = await browser_get_text(make_ctx())
        assert "Example Domain" in result
        assert "use in documentation examples" in result.lower()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_launch_twice_is_idempotent(self):
        await browser_launch(make_ctx())
        result = await browser_launch(make_ctx())
        assert "already launched" in result.lower()
