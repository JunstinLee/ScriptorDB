from __future__ import annotations

"""浏览器接管操作面：编排器依赖该接口而非 browser 包。"""

from typing import Protocol


class TakeoverController(Protocol):
    """编排器对浏览器接管状态机的操作面（解耦 browser 包直接依赖）。"""

    def complete(self, result: str) -> None: ...
    def cancel(self, reason: str = "") -> None: ...
    def reset(self) -> None: ...


class _BrowserTakeoverController:
    """默认实现：代理到全局浏览器管理器（延迟导入，与原有行为一致）。"""

    def complete(self, result: str) -> None:
        from browser import get_manager
        mgr = get_manager()
        mgr.takeover.complete(result)
        mgr.clear_auth_challenge()

    def cancel(self, reason: str = "") -> None:
        from browser import get_manager
        mgr = get_manager()
        mgr.takeover.cancel(reason)
        mgr.clear_auth_challenge()

    def reset(self) -> None:
        from browser import get_manager
        get_manager().takeover.reset()
