from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser import get_manager
from tools.browser import (
    browser_evaluate,
    browser_load_state,
    browser_query,
    browser_screenshot,
    browser_scroll,
)


@pytest.fixture(autouse=True)
def _cleanup_browser():
    get_manager().reset()
    yield
    get_manager().reset()


class TestBrowserLoadState:
    @pytest.mark.asyncio
    async def test_load_state_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_load_state(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_load_state_load(self):
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_load_state(None, "load")
            assert "reached load state" in result.lower()
            assert "load" in result
            mock_page.wait_for_load_state.assert_awaited_once_with("load")

    @pytest.mark.asyncio
    async def test_load_state_networkidle(self):
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_load_state(None, "networkidle")
            assert "reached load state" in result.lower()
            assert "networkidle" in result
            mock_page.wait_for_load_state.assert_awaited_once_with("networkidle")


class TestBrowserEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_evaluate(None, "document.title")
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_evaluate_returns_result(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="Apple")
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_evaluate(None, "document.title")
            assert "Apple" in result
            mock_page.evaluate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_error(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(side_effect=Exception("eval error"))
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_evaluate(None, "bad.code")
            assert "error" in result.lower()


class TestBrowserQuery:
    @pytest.mark.asyncio
    async def test_query_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_query(None, "h1")
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_query_text_single(self):
        mock_element = AsyncMock()
        mock_element.inner_text = AsyncMock(return_value="Hello World")

        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_query(None, "h1")
            assert "Hello World" in result
            mock_page.query_selector.assert_awaited_once_with("h1")

    @pytest.mark.asyncio
    async def test_query_text_all(self):
        mock_el_0 = AsyncMock()
        mock_el_0.inner_text = AsyncMock(return_value="First")
        mock_el_1 = AsyncMock()
        mock_el_1.inner_text = AsyncMock(return_value="Second")

        mock_page = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_el_0, mock_el_1])

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_query(None, "li", all=True)
            assert "[0] First" in result
            assert "[1] Second" in result
            mock_page.query_selector_all.assert_awaited_once_with("li")

    @pytest.mark.asyncio
    async def test_query_attr_single(self):
        mock_element = AsyncMock()
        mock_element.get_attribute = AsyncMock(return_value="https://example.com")

        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_query(None, "a", attribute="href")
            assert "https://example.com" in result
            mock_page.query_selector.assert_awaited_once_with("a")

    @pytest.mark.asyncio
    async def test_query_no_match(self):
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_query(None, ".nonexistent")
            assert "No element found" in result


class TestBrowserQueryImages:
    @pytest.mark.asyncio
    async def test_query_images(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=["/img/a.png", "/img/b.png"])

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_query(None, "img[src]", attribute="src", all=True)
            assert "[0] /img/a.png" in result
            assert "[1] /img/b.png" in result

    @pytest.mark.asyncio
    async def test_query_images_empty(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[])

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_query(None, "img[src]", attribute="src", all=True)
            assert "no images" in result.lower()


class TestBrowserScroll:
    @pytest.mark.asyncio
    async def test_scroll_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_scroll(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_scroll_to_bottom(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_scroll(None, to_bottom=True)
            assert "bottom" in result.lower()
            mock_page.evaluate.assert_awaited_once()
            mock_page.wait_for_timeout.assert_awaited_once_with(500)

    @pytest.mark.asyncio
    async def test_scroll_by_pixels(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_scroll(None, to_bottom=False, pixels=300)
            assert "300px" in result
            mock_page.wait_for_timeout.assert_awaited_once_with(300)


class TestBrowserScreenshot:
    @pytest.mark.asyncio
    async def test_screenshot_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_screenshot(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_screenshot_saves_file(self):
        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_screenshot(None, "/tmp/test.png")
            assert "Screenshot saved to /tmp/test.png" in result
            mock_page.screenshot.assert_awaited_once_with(path="/tmp/test.png", full_page=True)

    @pytest.mark.asyncio
    async def test_screenshot_default_path(self):
        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()

        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_screenshot(None)
            assert "Screenshot saved to" in result
            assert "outputs/browser/" in result
            mock_page.screenshot.assert_awaited_once()


class TestBrowserDynamicRender:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_apple_dynamic_render(self):
        from tools.browser import browser_launch, browser_navigate, browser_get_text

        result = await browser_launch(None)
        assert "launched successfully" in result.lower()

        result = await browser_navigate(None, "https://www.apple.com")
        assert "navigated to" in result.lower()

        result = await browser_load_state(None, "networkidle")
        assert "reached load state" in result.lower()

        result = await browser_evaluate(None, "document.title")
        assert "Apple" in result

        result = await browser_query(None, "h1")
        assert len(result) > 0

        result = await browser_query(None, "img[src]", attribute="src", all=True)
        assert len(result) > 0

        result = await browser_scroll(None, to_bottom=True)
        assert "bottom" in result.lower()

        result = await browser_screenshot(None, "outputs/browser/apple_test.png")
        assert "Screenshot saved to" in result
