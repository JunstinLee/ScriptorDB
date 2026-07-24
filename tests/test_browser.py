from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

import pytest

from browser import get_manager
from tools.browser import (
    browser_get_text,
    browser_launch,
    browser_navigate,
)


@pytest.fixture(autouse=True)
def _cleanup_browser():
    get_manager().reset()
    yield
    get_manager().reset()


class TestBrowserLaunch:
    @pytest.mark.asyncio
    async def test_launch_without_playwright_installed(self):
        saved = {}
        for key in list(sys.modules.keys()):
            if key.startswith("playwright"):
                saved[key] = sys.modules.pop(key)
        try:
            with patch("builtins.__import__", side_effect=ImportError("No module named 'playwright'")):
                result = await browser_launch(None)
                assert "not installed" in result.lower()
        finally:
            sys.modules.update(saved)

    @pytest.mark.asyncio
    async def test_launch_already_running(self):
        mock_browser = AsyncMock()
        with patch.object(get_manager(), "_browser", mock_browser):
            result = await browser_launch(None)
            assert "already launched" in result.lower()

    @pytest.mark.asyncio
    async def test_launch_success(self):
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_ap = AsyncMock()
        mock_ap.start.return_value = mock_playwright

        mgr = get_manager()
        with patch.object(mgr, "_browser", None), \
             patch.object(mgr, "_playwright", None), \
             patch("playwright.async_api.async_playwright", return_value=mock_ap):
            result = await browser_launch(None)
            assert "launched successfully" in result.lower()


class TestBrowserNavigate:
    @pytest.mark.asyncio
    async def test_navigate_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_navigate(None, "http://example.com")
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_navigate_success(self):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_navigate(None, "http://example.com")
            assert "navigated to" in result.lower()
            mock_page.goto.assert_awaited_once_with("http://example.com", wait_until="domcontentloaded")


class TestBrowserGetText:
    @pytest.mark.asyncio
    async def test_get_text_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_get_text(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_get_text_success(self):
        mock_page = AsyncMock()
        mock_page.title.return_value = "Example Domain"
        mock_page.inner_text.return_value = "This domain is for use in documentation examples"
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_get_text(None)
            assert "# Example Domain" in result
            assert "documentation examples" in result


class TestBrowserIntegration:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_real_browser_launch_navigate_and_get_text(self):
        result = await browser_launch(None)
        assert "launched successfully" in result.lower()

        result = await browser_navigate(None, "http://example.com")
        assert "navigated to" in result.lower()

        result = await browser_get_text(None)
        assert "Example Domain" in result
        assert "use in documentation examples" in result.lower()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_launch_twice_is_idempotent(self):
        await browser_launch(None)
        result = await browser_launch(None)
        assert "already launched" in result.lower()
