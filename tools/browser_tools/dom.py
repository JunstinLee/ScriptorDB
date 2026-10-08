"""向后兼容 shim：DOM 读取类工具已拆分。

- browser_find → :mod:`tools.browser_tools.find`
- browser_read → :mod:`tools.browser_tools.read`

本模块只做 re-export，勿在此新增逻辑。
"""

from __future__ import annotations

from tools.browser_tools.find import (  # noqa: F401  (re-export)
    _find_containers,
    _find_elements,
    browser_find,
)
from tools.browser_tools.read import browser_read  # noqa: F401  (re-export)

__all__ = ["browser_find", "browser_read"]
