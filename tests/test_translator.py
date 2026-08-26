from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import patch

import pytest
from pydantic_ai.messages import (
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from runtime.run_tracker import RunTracker
from runtime.runner.translator import EventTranslator


@pytest.mark.asyncio
async def test_translator_keeps_part_start_first_fragment():
    """回归：每个 TextPart 的首分片由 PartStartEvent 承载，必须进入 full_output。

    修复前 _handle_text_delta 只消费 PartDeltaEvent(TextPartDelta)，
    PartStartEvent 的首分片被静默丢弃，导致落盘内容每段开头缺字。
    """
    queue: asyncio.Queue[dict] = asyncio.Queue()
    tracker = RunTracker()
    translator = EventTranslator(
        queue=queue,
        tracker=tracker,
        checkpoint_id="test",
        prompt="",
        message_history=[],
    )

    async def events():
        yield PartStartEvent(index=0, part=TextPart(content="Data "))
        yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Subtype 已加载选项 1-6。"))
        yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="让我查看这些选项的文本标签。"))

    await translator.handle(cast(Any, None), events())

    expected = "Data Subtype 已加载选项 1-6。让我查看这些选项的文本标签。"
    assert tracker.final_output == expected

    deltas = []
    while not queue.empty():
        ev = queue.get_nowait()
        if ev["type"] == "text_delta":
            deltas.append(ev["delta"])
    assert deltas == ["Data ", "Subtype 已加载选项 1-6。", "让我查看这些选项的文本标签。"]


@pytest.mark.asyncio
async def test_translator_part_start_without_deltas_is_kept():
    """整段内容都在 PartStartEvent 里（无后续 delta）时也必须完整保留。"""
    queue: asyncio.Queue[dict] = asyncio.Queue()
    tracker = RunTracker()
    translator = EventTranslator(
        queue=queue,
        tracker=tracker,
        checkpoint_id="test",
        prompt="",
        message_history=[],
    )

    async def events():
        yield PartStartEvent(index=0, part=TextPart(content="预览加载成功！"))

    await translator.handle(cast(Any, None), events())

    assert tracker.final_output == "预览加载成功！"

    deltas = []
    while not queue.empty():
        ev = queue.get_nowait()
        if ev["type"] == "text_delta":
            deltas.append(ev["delta"])
    assert deltas == ["预览加载成功！"]


@pytest.mark.asyncio
async def test_translator_unknown_event_type_warns_not_raises():
    """未识别的事件类型走 warning 分支：不静默吞掉、不抛错。"""
    queue: asyncio.Queue[dict] = asyncio.Queue()
    tracker = RunTracker()
    translator = EventTranslator(
        queue=queue,
        tracker=tracker,
        checkpoint_id="test",
        prompt="",
        message_history=[],
    )

    class UnknownEvent:
        pass

    async def events():
        yield UnknownEvent()

    with patch("runtime.runner.translator.logger.warning") as mock_warn:
        await translator.handle(cast(Any, None), events())

    assert tracker.final_output == ""
    assert queue.empty()
    mock_warn.assert_called_once()
    assert "unhandled run event type" in mock_warn.call_args[0][0]
