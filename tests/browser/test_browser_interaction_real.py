from __future__ import annotations

import pytest

from tests.support.ctx import make_ctx

pytestmark = [
    pytest.mark.slow,
    pytest.mark.usefixtures("cleanup_browser"),
]


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

        result = await browser_launch(make_ctx())
        assert "launched" in result.lower()

        result = await browser_navigate(
            None, "https://todomvc.com/examples/react/dist/"
        )
        assert "navigated" in result.lower()

        result = await browser_load_state(make_ctx(), "networkidle")
        assert "load state" in result.lower() or "networkidle" in result

        result = await browser_wait_for_selector(make_ctx(), ".new-todo")
        assert "visible" in result.lower() or "Element" in result

        result = await browser_fill(make_ctx(), ".new-todo", "Buy milk")
        assert "Buy milk" in result

        result = await browser_press_key(make_ctx(), "Enter")
        assert "Pressed" in result or "Enter" in result

        result = await browser_query(make_ctx(), ".todo-list li")
        assert "Buy milk" in result

        result = await browser_click(make_ctx(), ".todo-list li .toggle")
        assert "Clicked" in result or "toggle" in result

        result = await browser_query(make_ctx(), ".todo-list li", attribute="class")
        assert "completed" in result

        result = await browser_fill(make_ctx(), ".new-todo", "Read book")
        assert "Read book" in result

        result = await browser_press_key(make_ctx(), "Enter")
        assert "Pressed" in result or "Enter" in result

        result = await browser_query(make_ctx(), ".todo-list li", all=True)
        assert "Buy milk" in result
        assert "Read book" in result

        result = await browser_click(make_ctx(), ".clear-completed")
        assert "Clicked" in result or "clear-completed" in result

        result = await browser_query(make_ctx(), ".todo-list li", all=True)
        assert "Buy milk" not in result
        assert "Read book" in result

        result = await browser_screenshot(make_ctx(), "outputs/browser/todomvc_test.png")
        assert "Screenshot saved" in result
