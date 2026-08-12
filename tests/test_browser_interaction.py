from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from browser import get_manager
from tests.conftest import _make_ctx
from tools.browser import (
    browser_click,
    browser_fill,
    browser_press_key,
    browser_wait_for_selector,
)


pytestmark = pytest.mark.usefixtures("cleanup_browser")


class TestBrowserWaitForSelector:
    @pytest.mark.asyncio
    async def test_wait_for_selector_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_wait_for_selector(_make_ctx(), ".new-todo")
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_wait_for_selector_visible(self):
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_wait_for_selector(_make_ctx(), ".new-todo")
            assert "visible" in result.lower()
            assert ".new-todo" in result
            mock_page.wait_for_selector.assert_awaited_once_with(
                ".new-todo", state="visible", timeout=10_000
            )

    @pytest.mark.asyncio
    async def test_wait_for_selector_hidden(self):
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_wait_for_selector(_make_ctx(), ".loading", state="hidden")
            assert "hidden" in result.lower()
            assert ".loading" in result
            mock_page.wait_for_selector.assert_awaited_once_with(
                ".loading", state="hidden", timeout=10_000
            )

    @pytest.mark.asyncio
    async def test_wait_for_selector_timeout(self):
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(
            side_effect=TimeoutError("Timeout 10000ms exceeded")
        )
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_wait_for_selector(_make_ctx(), ".never")
            assert "Timeout" in result or "now visible" in result


class TestBrowserClick:
    @pytest.mark.asyncio
    async def test_click_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_click(_make_ctx(), ".button")
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_click_success(self):
        mock_page = AsyncMock()
        mock_page.click = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_click(_make_ctx(), ".button")
            assert "Clicked" in result
            assert ".button" in result
            mock_page.click.assert_awaited_once_with(".button")

    @pytest.mark.asyncio
    async def test_click_element_not_found(self):
        mock_page = AsyncMock()
        mock_page.click = AsyncMock(side_effect=Exception("Element not found"))
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_click(_make_ctx(), ".missing")
            assert "failed" in result.lower() or "element" in result.lower()


class TestBrowserFill:
    @pytest.mark.asyncio
    async def test_fill_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_fill(_make_ctx(), "input", "hello")
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_fill_success(self):
        mock_page = AsyncMock()
        mock_page.fill = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_fill(_make_ctx(), "input", "hello world")
            assert "Filled" in result
            assert "input" in result
            assert "hello world" in result
            mock_page.fill.assert_awaited_once_with("input", "hello world")

    @pytest.mark.asyncio
    async def test_fill_element_not_found(self):
        mock_page = AsyncMock()
        mock_page.fill = AsyncMock(side_effect=Exception("Element not found"))
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_fill(_make_ctx(), ".missing", "text")
            assert "failed" in result.lower() or "element" in result.lower()


class TestBrowserPressKey:
    @pytest.mark.asyncio
    async def test_press_key_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_press_key(_make_ctx(), "Enter")
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_press_key_enter(self):
        mock_page = AsyncMock()
        mock_page.keyboard = AsyncMock()
        mock_page.keyboard.press = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_press_key(_make_ctx(), "Enter")
            assert "Pressed" in result
            assert "Enter" in result
            mock_page.keyboard.press.assert_awaited_once_with("Enter")

    @pytest.mark.asyncio
    async def test_press_key_escape(self):
        mock_page = AsyncMock()
        mock_page.keyboard = AsyncMock()
        mock_page.keyboard.press = AsyncMock()
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_press_key(_make_ctx(), "Escape")
            assert "Pressed" in result
            assert "Escape" in result
            mock_page.keyboard.press.assert_awaited_once_with("Escape")

    @pytest.mark.asyncio
    async def test_press_key_error(self):
        mock_page = AsyncMock()
        mock_page.keyboard = AsyncMock()
        mock_page.keyboard.press = AsyncMock(side_effect=Exception("Keyboard error"))
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_press_key(_make_ctx(), "F99")
            assert "failed" in result.lower() or "error" in result.lower()


class TestBrowserInteraction:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_todomvc_interaction(self):
        from tools.browser import (
            browser_click,
            browser_fill,
            browser_launch,
            browser_load_state,
            browser_navigate,
            browser_press_key,
            browser_query,
            browser_screenshot,
            browser_wait_for_selector,
        )

        result = await browser_launch(_make_ctx())
        assert "launched" in result.lower()

        result = await browser_navigate(
            None, "https://todomvc.com/examples/react/dist/"
        )
        assert "navigated" in result.lower()

        result = await browser_load_state(_make_ctx(), "networkidle")
        assert "load state" in result.lower() or "networkidle" in result

        result = await browser_wait_for_selector(_make_ctx(), ".new-todo")
        assert "visible" in result.lower() or "Element" in result

        result = await browser_fill(_make_ctx(), ".new-todo", "Buy milk")
        assert "Buy milk" in result

        result = await browser_press_key(_make_ctx(), "Enter")
        assert "Pressed" in result or "Enter" in result

        result = await browser_query(_make_ctx(), ".todo-list li")
        assert "Buy milk" in result

        result = await browser_click(_make_ctx(), ".todo-list li .toggle")
        assert "Clicked" in result or "toggle" in result

        result = await browser_query(_make_ctx(), ".todo-list li", attribute="class")
        assert "completed" in result

        result = await browser_fill(_make_ctx(), ".new-todo", "Read book")
        assert "Read book" in result

        result = await browser_press_key(_make_ctx(), "Enter")
        assert "Pressed" in result or "Enter" in result

        result = await browser_query(_make_ctx(), ".todo-list li", all=True)
        assert "Buy milk" in result
        assert "Read book" in result

        result = await browser_click(_make_ctx(), ".clear-completed")
        assert "Clicked" in result or "clear-completed" in result

        result = await browser_query(_make_ctx(), ".todo-list li", all=True)
        assert "Buy milk" not in result
        assert "Read book" in result

        result = await browser_screenshot(_make_ctx(), "outputs/browser/todomvc_test.png")
        assert "Screenshot saved" in result
