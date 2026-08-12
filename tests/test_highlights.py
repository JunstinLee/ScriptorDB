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


@pytest.mark.parametrize(
    ("action", "kwargs", "min_calls"),
    [
        (inject_highlight_runtime, {}, 1),
        (highlight_click, {"selector": "#test", "duration_ms": 10}, 3),
        (highlight_input, {"selector": "#test"}, 1),
        (highlight_input_remove, {}, 1),
        (highlight_scroll, {"pixels": 100}, 3),
    ],
)
async def test_highlight_does_not_crash(action, kwargs, min_calls):
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    await action(page, **kwargs)
    assert page.evaluate.call_count >= min_calls


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
