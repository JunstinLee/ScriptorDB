from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from browser import get_manager
from tools.browser import (
    browser_clear_cookies,
    browser_get_cookies,
    browser_get_url,
    browser_go_back,
    browser_go_forward,
    browser_set_cookies,
)


@pytest.fixture(autouse=True)
def _cleanup_browser():
    get_manager().reset()
    yield
    get_manager().reset()


class TestBrowserGetCookies:
    @pytest.mark.asyncio
    async def test_get_cookies_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_get_cookies(None)
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
            result = await browser_get_cookies(None)
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
            result = await browser_get_cookies(None)
            assert result == "No cookies found"


class TestBrowserSetCookies:
    @pytest.mark.asyncio
    async def test_set_cookies_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_set_cookies(None, '[{"name":"a"}]')
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
            result = await browser_set_cookies(None, "not valid json")
            assert "Invalid cookies JSON" in result


class TestBrowserClearCookies:
    @pytest.mark.asyncio
    async def test_clear_cookies_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_clear_cookies(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_clear_cookies_success(self):
        mock_page = AsyncMock()
        mock_page.context = AsyncMock()
        mock_page.context.clear_cookies = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_clear_cookies(None)
            assert result == "All cookies cleared"
            mock_page.context.clear_cookies.assert_awaited_once()


class TestBrowserGetUrl:
    @pytest.mark.asyncio
    async def test_get_url_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_get_url(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_get_url_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://github.com"
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_get_url(None)
            assert result == "https://github.com"


class TestBrowserGoBack:
    @pytest.mark.asyncio
    async def test_go_back_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_go_back(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_go_back_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://google.com/search"
        mock_page.go_back = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_go_back(None)
            assert "Navigated back" in result
            assert "google.com/search" in result
            mock_page.go_back.assert_awaited_once()


class TestBrowserGoForward:
    @pytest.mark.asyncio
    async def test_go_forward_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_go_forward(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_go_forward_success(self):
        mock_page = AsyncMock()
        mock_page.url = "https://github.com/login"
        mock_page.go_forward = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_go_forward(None)
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

        result = await browser_launch(None)
        assert "launched" in result.lower()

        result = await browser_navigate(None, "https://github.com/login")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(None, "#login_field")
        assert "visible" in result.lower()
        result = await browser_wait_for_selector(None, "#password")
        assert "visible" in result.lower()

        result = await browser_get_url(None)
        assert "github.com/login" in result

        result = await browser_fill(None, "#login_field", "test@example.com")
        assert "Filled" in result
        result = await browser_fill(None, "#password", "placeholder")
        assert "Filled" in result

        result = await browser_get_cookies(None)
        assert len(result) > 0

        result = await browser_clear_cookies(None)
        assert "cleared" in result.lower()

        result = await browser_navigate(None, "https://github.com/login")
        result = await browser_wait_for_selector(None, "#login_field")
        result = await browser_evaluate(None, "document.querySelector('#login_field').value")
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

        result = await browser_launch(None)
        assert "launched" in result.lower()
        result = await browser_navigate(None, "https://www.google.com")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(None, "textarea[name=q]")
        assert "visible" in result.lower() or "now" in result.lower()

        result = await browser_fill(None, "textarea[name=q]", "pydantic ai github")
        assert "Filled" in result
        result = await browser_press_key(None, "Enter")

        result = await browser_wait_for_selector(None, "#search")
        assert "visible" in result.lower() or "now" in result.lower()

        result = await browser_get_text(None)
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

        result = await browser_launch(None)
        assert "launched" in result.lower()
        result = await browser_navigate(None, "https://www.amazon.com")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(None, "#twotabsearchtextbox")
        assert "visible" in result.lower()
        result = await browser_fill(None, "#twotabsearchtextbox", "laptop")
        assert "Filled" in result
        result = await browser_press_key(None, "Enter")

        result = await browser_wait_for_selector(
            None, "[data-component-type='s-search-result'] h2 span"
        )
        result = await browser_query(
            None, "[data-component-type='s-search-result'] h2 span", all=True
        )
        assert len(result) > 0

        result = await browser_scroll(None, to_bottom=True)
        assert "bottom" in result.lower()

        result = await browser_screenshot(None, "outputs/browser/amazon_search.png")
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

        result = await browser_launch(None)
        assert "launched" in result.lower()
        result = await browser_navigate(None, "https://www.notion.so/login")
        assert "navigated" in result.lower()

        result = await browser_get_url(None)
        assert "notion" in result.lower() and "login" in result.lower()

        result = await browser_wait_for_selector(None, "input[type=email]")
        result = await browser_fill(None, "input[type=email]", "test@example.com")
        assert "Filled" in result

        result = await browser_press_key(None, "Enter")

        result = await browser_get_text(None)
        assert len(result) > 0

        result = await browser_screenshot(None, "outputs/browser/notion_login.png")
        assert "Screenshot saved" in result
