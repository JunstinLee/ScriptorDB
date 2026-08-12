from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from browser import get_manager
from tests.conftest import _make_ctx
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
            result = await browser_get_cookies(_make_ctx())
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
            result = await browser_get_cookies(_make_ctx())
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
            result = await browser_get_cookies(_make_ctx())
            assert result == "No cookies found"


class TestBrowserSetCookies:
    @pytest.mark.asyncio
    async def test_set_cookies_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_set_cookies(_make_ctx(), '[{"name":"a"}]')
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
            result = await browser_set_cookies(_make_ctx(), "not valid json")
            assert "Invalid cookies JSON" in result


class TestBrowserClearCookies:
    @pytest.mark.asyncio
    async def test_clear_cookies_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_clear_cookies(_make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_clear_cookies_success(self):
        mock_page = AsyncMock()
        mock_page.context = AsyncMock()
        mock_page.context.clear_cookies = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_clear_cookies(_make_ctx())
            assert result == "All cookies cleared"
            mock_page.context.clear_cookies.assert_awaited_once()


class TestBrowserGetUrl:
    @pytest.mark.asyncio
    async def test_get_url_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_get_url(_make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_get_url_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://github.com"
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_get_url(_make_ctx())
            assert result == "https://github.com"


class TestBrowserGoBack:
    @pytest.mark.asyncio
    async def test_go_back_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_go_back(_make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_go_back_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://google.com/search"
        mock_page.go_back = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_go_back(_make_ctx())
            assert "Navigated back" in result
            assert "google.com/search" in result
            mock_page.go_back.assert_awaited_once()


class TestBrowserGoForward:
    @pytest.mark.asyncio
    async def test_go_forward_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_go_forward(_make_ctx())
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_go_forward_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://github.com/login"
        mock_page.go_forward = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_go_forward(_make_ctx())
            assert "Navigated forward" in result
            assert "github.com/login" in result
            mock_page.go_forward.assert_awaited_once()


class TestBrowserBusinessIntegration:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_github_login_cookie_persistence(self):
        from tools.browser import (
            browser_clear_cookies,
            browser_evaluate,
            browser_fill,
            browser_get_cookies,
            browser_get_url,
            browser_launch,
            browser_navigate,
            browser_wait_for_selector,
        )

        result = await browser_launch(_make_ctx())
        assert "launched" in result.lower()

        result = await browser_navigate(_make_ctx(), "https://github.com/login")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(_make_ctx(), "#login_field")
        assert "visible" in result.lower()
        result = await browser_wait_for_selector(_make_ctx(), "#password")
        assert "visible" in result.lower()

        result = await browser_get_url(_make_ctx())
        assert "github.com/login" in result

        result = await browser_fill(_make_ctx(), "#login_field", "test@example.com")
        assert "Filled" in result
        result = await browser_fill(_make_ctx(), "#password", "placeholder")
        assert "Filled" in result

        result = await browser_get_cookies(_make_ctx())
        assert len(result) > 0

        result = await browser_clear_cookies(_make_ctx())
        assert "cleared" in result.lower()

        result = await browser_navigate(_make_ctx(), "https://github.com/login")
        result = await browser_wait_for_selector(_make_ctx(), "#login_field")
        result = await browser_evaluate(_make_ctx(), "document.querySelector('#login_field').value")
        assert result == '""'

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_google_search_and_navigation(self):
        from tools.browser import (
            browser_fill,
            browser_get_text,
            browser_get_url,
            browser_launch,
            browser_navigate,
            browser_press_key,
            browser_wait_for_selector,
        )

        result = await browser_launch(_make_ctx())
        assert "launched" in result.lower()
        result = await browser_navigate(_make_ctx(), "https://www.google.com")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(_make_ctx(), "textarea[name=q]")
        assert "visible" in result.lower() or "now" in result.lower()

        result = await browser_fill(_make_ctx(), "textarea[name=q]", "pydantic ai github")
        assert "Filled" in result
        result = await browser_press_key(_make_ctx(), "Enter")

        result = await browser_wait_for_selector(_make_ctx(), "#search")
        assert "visible" in result.lower() or "now" in result.lower()

        result = await browser_get_text(_make_ctx())
        assert "pydantic" in result.lower() or "github" in result.lower()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_amazon_search_and_product_list(self):
        from tools.browser import (
            browser_fill,
            browser_get_url,
            browser_launch,
            browser_navigate,
            browser_press_key,
            browser_query,
            browser_screenshot,
            browser_scroll,
            browser_wait_for_selector,
        )

        result = await browser_launch(_make_ctx())
        assert "launched" in result.lower()
        result = await browser_navigate(_make_ctx(), "https://www.amazon.com")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(_make_ctx(), "#twotabsearchtextbox")
        assert "visible" in result.lower()
        result = await browser_fill(_make_ctx(), "#twotabsearchtextbox", "laptop")
        assert "Filled" in result
        result = await browser_press_key(_make_ctx(), "Enter")

        result = await browser_wait_for_selector(
            None, "[data-component-type='s-search-result'] h2 span"
        )
        result = await browser_query(
            None, "[data-component-type='s-search-result'] h2 span", all=True
        )
        assert len(result) > 0

        result = await browser_scroll(_make_ctx(), to_bottom=True)
        assert "bottom" in result.lower()

        result = await browser_screenshot(_make_ctx(), "outputs/browser/amazon_search.png")
        assert "Screenshot saved" in result

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_notion_login_page_interaction(self):
        from tools.browser import (
            browser_fill,
            browser_get_text,
            browser_get_url,
            browser_launch,
            browser_navigate,
            browser_press_key,
            browser_screenshot,
            browser_wait_for_selector,
        )

        result = await browser_launch(_make_ctx())
        assert "launched" in result.lower()
        result = await browser_navigate(_make_ctx(), "https://www.notion.so/login")
        assert "navigated" in result.lower()

        result = await browser_get_url(_make_ctx())
        assert "notion" in result.lower() and "login" in result.lower()

        result = await browser_wait_for_selector(_make_ctx(), "input[type=email]")
        result = await browser_fill(_make_ctx(), "input[type=email]", "test@example.com")
        assert "Filled" in result

        result = await browser_press_key(_make_ctx(), "Enter")

        result = await browser_get_text(_make_ctx())
        assert len(result) > 0

        result = await browser_screenshot(_make_ctx(), "outputs/browser/notion_login.png")
        assert "Screenshot saved" in result
