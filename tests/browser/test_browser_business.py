from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from browser import get_manager
from tests.support.ctx import make_ctx
from tools.browser import (
    browser_clear_cookies,
    browser_get_cookies,
    browser_get_url,
    browser_go_back,
    browser_go_forward,
    browser_set_cookies,
)


pytestmark = pytest.mark.usefixtures("cleanup_browser")


class TestBrowserGetCookies:
    @pytest.mark.asyncio
    async def test_get_cookies_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_get_cookies(make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_get_cookies_success(self):
        mock_page = AsyncMock()
        mock_page.context = AsyncMock()
        mock_page.context.cookies = AsyncMock(
            return_value=[
                {"name": "session", "value": "abc123", "domain": "example.com"},
                {"name": "token", "value": "xyz789", "domain": "example.com"},
            ]
        )
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_get_cookies(make_ctx())
            assert "session" in result
            assert "abc123" in result
            assert "token" in result
            assert "xyz789" in result

    @pytest.mark.asyncio
    async def test_get_cookies_empty(self):
        mock_page = AsyncMock()
        mock_page.context = AsyncMock()
        mock_page.context.cookies = AsyncMock(return_value=[])
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_get_cookies(make_ctx())
            assert result == "No cookies found"


class TestBrowserSetCookies:
    @pytest.mark.asyncio
    async def test_set_cookies_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_set_cookies(make_ctx(), '[{"name":"a"}]')
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_set_cookies_success(self):
        mock_page = AsyncMock()
        mock_page.context = AsyncMock()
        mock_page.context.add_cookies = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_set_cookies(
                None, '[{"name":"session","value":"abc"}]'
            )
            assert "Set" in result
            assert "1 cookie" in result
            mock_page.context.add_cookies.assert_awaited_once_with(
                [{"name": "session", "value": "abc"}]
            )

    @pytest.mark.asyncio
    async def test_set_cookies_invalid_json(self):
        mock_page = AsyncMock()
        mock_page.context = AsyncMock()
        mock_page.context.add_cookies = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_set_cookies(make_ctx(), "not valid json")
            assert "Invalid cookies JSON" in result


class TestBrowserClearCookies:
    @pytest.mark.asyncio
    async def test_clear_cookies_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_clear_cookies(make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_clear_cookies_success(self):
        mock_page = AsyncMock()
        mock_page.context = AsyncMock()
        mock_page.context.clear_cookies = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_clear_cookies(make_ctx())
            assert result == "All cookies cleared"
            mock_page.context.clear_cookies.assert_awaited_once()


class TestBrowserGetUrl:
    @pytest.mark.asyncio
    async def test_get_url_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_get_url(make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_get_url_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://github.com"
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_get_url(make_ctx())
            assert result == "https://github.com"


class TestBrowserGoBack:
    @pytest.mark.asyncio
    async def test_go_back_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_go_back(make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_go_back_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://google.com/search"
        mock_page.go_back = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_go_back(make_ctx())
            assert "Navigated back" in result
            assert "google.com/search" in result
            mock_page.go_back.assert_awaited_once()


class TestBrowserGoForward:
    @pytest.mark.asyncio
    async def test_go_forward_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_go_forward(make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_go_forward_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://github.com/login"
        mock_page.go_forward = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_go_forward(make_ctx())
            assert "Navigated forward" in result
            assert "github.com/login" in result
            mock_page.go_forward.assert_awaited_once()

