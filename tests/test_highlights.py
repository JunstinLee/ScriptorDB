from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from browser.highlights import (
    highlight_click,
    highlight_input,
    highlight_input_remove,
    highlight_scroll,
    inject_highlight_runtime,
)


@pytest.mark.asyncio
async def test_inject_does_not_crash():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    await inject_highlight_runtime(page)
    page.evaluate.assert_called()


@pytest.mark.asyncio
async def test_highlight_click_does_not_crash():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    await highlight_click(page, "#test", duration_ms=10)
    assert page.evaluate.call_count >= 3


@pytest.mark.asyncio
async def test_highlight_input_does_not_crash():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    await highlight_input(page, "#test")
    page.evaluate.assert_called()


@pytest.mark.asyncio
async def test_highlight_input_remove_does_not_crash():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    await highlight_input_remove(page)
    page.evaluate.assert_called()


@pytest.mark.asyncio
async def test_highlight_scroll_does_not_crash():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    await highlight_scroll(page, 100)
    assert page.evaluate.call_count >= 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selector",
    [
        "input[name='q']",
        "input[name=\"q\"]",
        'input[name="va\\\\lue"]',
        "#id\\nwith\\nnewlines",
    ],
)
async def test_highlight_click_passes_selector_as_argument(selector):
    """Selector 必须作为 page.evaluate 的参数传递，不能出现在 JS 表达式中。"""
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    await highlight_click(page, selector, duration_ms=10)

    selector_calls = [
        call for call in page.evaluate.call_args_list if len(call.args) == 2
    ]
    assert selector_calls, "expected a page.evaluate(expression, selector) call"
    expression, arg = selector_calls[0].args
    assert arg == selector
    assert selector not in expression


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selector",
    [
        "input[name='q']",
        "input[name=\"q\"]",
        'input[name="va\\\\lue"]',
        "#id\\nwith\\nnewlines",
    ],
)
async def test_highlight_input_passes_selector_as_argument(selector):
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    await highlight_input(page, selector)

    selector_calls = [
        call for call in page.evaluate.call_args_list if len(call.args) == 2
    ]
    assert selector_calls, "expected a page.evaluate(expression, selector) call"
    expression, arg = selector_calls[0].args
    assert arg == selector
    assert selector not in expression
