"""中间件运行时状态：跨工具调用累积的进程级可变映射。

原先这些映射以四个独立模块级变量散落在 ``tool_middleware``；这里合并为一个
由单锁保护的 :class:`RoundState`。``blocks`` / ``browser_used`` / ``finds`` 按
轮次或 run 归组，超过 :data:`_MAX_ROUNDS` 时整体清空，避免长进程无界增长。
"""

from __future__ import annotations

import threading
from typing import Any

_MAX_ROUNDS = 1000


class RoundState:
    """进程级、跨工具调用共享的中间件状态。

    - ``blocks``：``round_id -> {tool_name: 拦截次数}``（switch / filter / ui-probe 熔断用）。
    - ``browser_used``：本回合是否已调用过浏览器工具（python 守卫观测用）。
    - ``detect_used``：本回合是否已跑过 ``browser_detect_filters``。
    - ``finds``：``run_key -> [find 记录]``（重复 find 熔断用）。
    - ``page_reads``：``run_key -> (page_key, nav_rev, content_rev, chars)``
      （重复整页读短路用）。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.blocks: dict[str, dict[str, int]] = {}
        self.browser_used: set[str] = set()
        self.detect_used: set[str] = set()
        self.finds: dict[str, list[dict[str, Any]]] = {}
        self.page_reads: dict[str, tuple] = {}

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    def bump_block(self, round_id: str, tool_name: str) -> int:
        """累加并返回某回合某工具的拦截次数。"""
        with self._lock:
            if len(self.blocks) > _MAX_ROUNDS:
                self.blocks.clear()
            counters = self.blocks.setdefault(round_id, {})
            counters[tool_name] = counters.get(tool_name, 0) + 1
            return counters[tool_name]

    def mark_browser_used(self, round_id: str) -> None:
        with self._lock:
            if len(self.browser_used) > _MAX_ROUNDS:
                self.browser_used.clear()
            self.browser_used.add(round_id)

    def browser_was_used(self, round_id: str) -> bool:
        return round_id in self.browser_used

    def mark_detect_used(self, round_id: str) -> None:
        self.detect_used.add(round_id)

    def detect_was_used(self, round_id: str) -> bool:
        return round_id in self.detect_used

    def add_find(self, run_key: str, record: dict[str, Any]) -> None:
        with self._lock:
            if len(self.finds) > _MAX_ROUNDS:
                self.finds.clear()
            self.finds.setdefault(run_key, []).append(record)

    def get_finds(self, run_key: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.finds.get(run_key, ()))

    def set_page_read(self, run_key: str, record: tuple) -> None:
        """记录一次整页读的 ``(page_key, nav_rev, content_rev, chars)``。"""
        with self._lock:
            if len(self.page_reads) > _MAX_ROUNDS:
                self.page_reads.clear()
            self.page_reads[run_key] = record

    def get_page_read(self, run_key: str) -> tuple | None:
        """取回上一次整页读的记录；无则 ``None``。"""
        with self._lock:
            return self.page_reads.get(run_key)

    def clear_run(self, run_key: str) -> None:
        with self._lock:
            self.finds.pop(run_key, None)
            self.page_reads.pop(run_key, None)


STATE = RoundState()
