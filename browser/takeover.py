from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum

from browser.human_detection import (  # noqa: F401  (re-export)
    HumanTrigger,
    detect_element_failure_trigger,
    detect_human_needed,
    detect_timeout_trigger,
)
from core.logging_setup import get_logger

logger = get_logger("browser.takeover")

__all__ = [
    "HumanTakeoverState",
    "HumanTakeoverManager",
    "TAKEOVER_TIMEOUT",
    "HumanTrigger",
    "detect_human_needed",
    "detect_timeout_trigger",
    "detect_element_failure_trigger",
]


class HumanTakeoverState(str, Enum):
    RUNNING = "running"
    DETECTED = "detected"
    WAITING_HUMAN = "waiting_human"
    HUMAN_CONTROL = "human_control"
    RESUMING = "resuming"
    CANCELLED = "cancelled"


TAKEOVER_TIMEOUT = 150


class HumanTakeoverManager:
    def __init__(self):
        self.state = HumanTakeoverState.RUNNING
        self.reason: str = ""
        self.trigger: str = ""
        self.current_url: str = ""
        self.result: str = ""
        self._detected_at: float = 0
        self._wait_start: float = 0
        self._timeout_task: asyncio.Task | None = None
        self._on_timeout: Callable | None = None
        self.message: str = ""

    def can_agent_proceed(self) -> bool:
        return self.state in (HumanTakeoverState.RUNNING, HumanTakeoverState.RESUMING)

    def should_pause_agent(self) -> bool:
        return self.state == HumanTakeoverState.DETECTED

    def is_paused(self) -> bool:
        return self.state in (HumanTakeoverState.WAITING_HUMAN, HumanTakeoverState.HUMAN_CONTROL)

    def request_takeover(self, reason: str, trigger: str = "",
                         url: str = "") -> bool:
        if self.state != HumanTakeoverState.RUNNING:
            return False
        self.state = HumanTakeoverState.DETECTED
        self.reason = reason
        self.trigger = trigger
        self.current_url = url
        self._detected_at = datetime.now(timezone.utc).timestamp()
        logger.warning(f"takeover requested reason={reason} trigger={trigger} url={url}")
        return True

    def retrigger(self, reason: str, trigger: str = "", url: str = "") -> bool:
        """DETECTED 态下替换触发原因（otp/填失败覆盖误触发）。

        状态机不变式：reason/trigger 只能由 request_takeover（RUNNING→DETECTED）
        或本方法（已 DETECTED）写入；不改变 state，也不管理 timeout（由
        enter_waiting 统一创建）。返回是否替换成功。
        """
        if self.state != HumanTakeoverState.DETECTED:
            return False
        self.reason = reason
        self.trigger = trigger
        if url:
            self.current_url = url
        logger.warning(f"takeover retriggered reason={reason} trigger={trigger}")
        return True

    def enter_waiting(self, on_timeout: Callable | None = None):
        self.state = HumanTakeoverState.WAITING_HUMAN
        self._wait_start = datetime.now(timezone.utc).timestamp()
        self._on_timeout = on_timeout
        logger.info("takeover enter waiting")
        if on_timeout:
            self._timeout_task = asyncio.create_task(self._timeout_loop())

    def enter_human_control(self):
        self._cancel_timeout()
        self.state = HumanTakeoverState.HUMAN_CONTROL
        self.message = "Operate in the Chrome window"
        logger.info("takeover enter human_control")

    def complete(self, result: str):
        self._cancel_timeout()
        self.state = HumanTakeoverState.RESUMING
        self.result = result
        logger.info(f"takeover complete result={result}")

    def cancel(self, reason: str = ""):
        self._cancel_timeout()
        self.state = HumanTakeoverState.CANCELLED
        logger.info(f"takeover cancelled reason={reason}")
        if reason:
            self.reason = reason

    def reset(self):
        self._cancel_timeout()
        self.state = HumanTakeoverState.RUNNING
        self.reason = ""
        self.trigger = ""
        self.result = ""
        self.message = ""
        self._detected_at = 0
        self._wait_start = 0

    def _cancel_timeout(self):
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None

    async def _timeout_loop(self):
        await asyncio.sleep(TAKEOVER_TIMEOUT)
        if self.state == HumanTakeoverState.WAITING_HUMAN:
            logger.warning(f"takeover timeout after {TAKEOVER_TIMEOUT}s")
            self.cancel(f"Timed out: no user response in {TAKEOVER_TIMEOUT}s")
            if self._on_timeout:
                self._on_timeout()


# 检测启发式（HumanTrigger / detect_human_needed / *_trigger）已移至
# browser/human_detection.py，此处仅 re-export（见文件顶部 import）。
