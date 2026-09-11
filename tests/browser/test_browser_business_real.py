from __future__ import annotations

import pytest

from tests.support.ctx import make_ctx

pytestmark = [
    pytest.mark.slow,
    pytest.mark.usefixtures("cleanup_browser"),
]


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

        result = await browser_launch(make_ctx())
        assert "launched" in result.lower()

        result = await browser_navigate(make_ctx(), "https://github.com/login")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(make_ctx(), "#login_field")
        assert "visible" in result.lower()
        result = await browser_wait_for_selector(make_ctx(), "#password")
        assert "visible" in result.lower()

        result = await browser_get_url(make_ctx())
        assert "github.com/login" in result

        result = await browser_fill(make_ctx(), "#login_field", "test@example.com")
        assert "Filled" in result
        result = await browser_fill(make_ctx(), "#password", "placeholder")
        assert "Filled" in result

        result = await browser_get_cookies(make_ctx())
        assert len(result) > 0

        result = await browser_clear_cookies(make_ctx())
        assert "cleared" in result.lower()

        result = await browser_navigate(make_ctx(), "https://github.com/login")
        result = await browser_wait_for_selector(make_ctx(), "#login_field")
        result = await browser_evaluate(make_ctx(), "document.querySelector('#login_field').value")
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

        result = await browser_launch(make_ctx())
        assert "launched" in result.lower()
        result = await browser_navigate(make_ctx(), "https://www.google.com")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(make_ctx(), "textarea[name=q]")
        assert "visible" in result.lower() or "now" in result.lower()

        result = await browser_fill(make_ctx(), "textarea[name=q]", "pydantic ai github")
        assert "Filled" in result
        result = await browser_press_key(make_ctx(), "Enter")

        result = await browser_wait_for_selector(make_ctx(), "#search")
        assert "visible" in result.lower() or "now" in result.lower()

        result = await browser_get_text(make_ctx())
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

        result = await browser_launch(make_ctx())
        assert "launched" in result.lower()
        result = await browser_navigate(make_ctx(), "https://www.amazon.com")
        assert "navigated" in result.lower()

        result = await browser_wait_for_selector(make_ctx(), "#twotabsearchtextbox")
        assert "visible" in result.lower()
        result = await browser_fill(make_ctx(), "#twotabsearchtextbox", "laptop")
        assert "Filled" in result
        result = await browser_press_key(make_ctx(), "Enter")

        result = await browser_wait_for_selector(
            None, "[data-component-type='s-search-result'] h2 span"
        )
        result = await browser_query(
            None, "[data-component-type='s-search-result'] h2 span", all=True
        )
        assert len(result) > 0

        result = await browser_scroll(make_ctx(), to_bottom=True)
        assert "bottom" in result.lower()

        result = await browser_screenshot(make_ctx(), "outputs/browser/amazon_search.png")
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

        result = await browser_launch(make_ctx())
        assert "launched" in result.lower()
        result = await browser_navigate(make_ctx(), "https://www.notion.so/login")
        assert "navigated" in result.lower()

        result = await browser_get_url(make_ctx())
        assert "notion" in result.lower() and "login" in result.lower()

        result = await browser_wait_for_selector(make_ctx(), "input[type=email]")
        result = await browser_fill(make_ctx(), "input[type=email]", "test@example.com")
        assert "Filled" in result

        result = await browser_press_key(make_ctx(), "Enter")

        result = await browser_get_text(make_ctx())
        assert len(result) > 0

        result = await browser_screenshot(make_ctx(), "outputs/browser/notion_login.png")
        assert "Screenshot saved" in result
