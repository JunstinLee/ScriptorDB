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
