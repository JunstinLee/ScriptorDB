from __future__ import annotations

from browser.manager import BrowserManager

__all__ = ["get_manager"]

_manager = BrowserManager()


def get_manager() -> BrowserManager:
    return _manager
