from __future__ import annotations

from browser.manager import BrowserManager
from browser.takeover import HumanTakeoverManager, HumanTakeoverState, HumanTrigger

__all__ = ["get_manager", "get_takeover_manager"]

_manager = BrowserManager()


def get_manager() -> BrowserManager:
    return _manager


def get_takeover_manager() -> HumanTakeoverManager:
    return _manager.takeover
