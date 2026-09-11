from __future__ import annotations

"""单次 run 的会话级事件总线：历史缓冲 + 多订阅者按游标重放。

run 的生存期不再由 SSE 响应生成器持有：订阅者可随时断开与重挂，事件在总线上
按绝对序号缓冲，重挂时用 `from_index` 游标增量重放。总线只承载 dict，SSE 编码
留在 API 层（`api/sse_format.sse_event`）。
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

# 展示层过滤：new_messages 由 run owner 直接落盘，无需经总线
_DROPPED_EVENT_TYPES = frozenset({"new_messages"})


class RunEventBus:
    """历史缓冲 + 多订阅者按游标重放，游标是绝对序号（不受截断影响）。"""

    def __init__(self, max_events: int = 500) -> None:
        self._max_events = max_events
        self._history: list[dict[str, Any]] = []
        # _history[0] 的绝对序号；超出上限时丢弃最旧事件并前移
        self._base_index = 0
        self._cond = asyncio.Condition()
        self._closed = False

    @property
    def last_index(self) -> int:
        """下一个事件的绝对序号（已发布事件总数）。"""
        return self._base_index + len(self._history)

    async def publish(self, event: dict[str, Any]) -> None:
        """追加事件到历史并唤醒订阅者。"""
        if event.get("type") in _DROPPED_EVENT_TYPES:
            return
        async with self._cond:
            self._history.append(event)
            dropped = len(self._history) - self._max_events
            if dropped > 0:
                del self._history[:dropped]
                self._base_index += dropped
            self._cond.notify_all()

    async def close(self) -> None:
        """终态：订阅者排空已有历史后结束。"""
        async with self._cond:
            self._closed = True
            self._cond.notify_all()

    async def subscribe(self, from_index: int = 0) -> AsyncIterator[tuple[int, dict[str, Any]]]:
        """从 from_index 起逐条 yield (绝对序号, 事件)，直到 close 后排空。"""
        cursor = max(from_index, self._base_index)
        if from_index < self._base_index:
            # 历史被截断：先告知订阅者拿到的是残缺历史，再从其起点续传
            yield self._base_index, {
                "type": "stream_truncated",
                "run_id": self._run_id(),
                "dropped_before": self._base_index,
            }
            cursor = self._base_index

        while True:
            async with self._cond:
                await self._cond.wait_for(
                    lambda: self.last_index > cursor or self._closed
                )
                if cursor < self._base_index:
                    # 消费期间发生截断：跳过已丢弃区间
                    cursor = self._base_index
                if cursor >= self.last_index:
                    # closed 且已排空
                    return
                index = cursor
                event = self._history[index - self._base_index]
                cursor += 1
            yield index, event

    def _run_id(self) -> str:
        for event in self._history:
            run_id = event.get("run_id")
            if run_id:
                return str(run_id)
        return ""
