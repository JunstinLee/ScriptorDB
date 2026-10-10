"""浏览器端注入脚本的资源加载器。

把大段嵌入式 JS 从 Python 源码中分离到 ``browser/scripts/*.js``，避免 JS
字符串污染 Python 模块。脚本按名缓存，只读一次磁盘。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent / "scripts"


@lru_cache(maxsize=None)
def load(name: str) -> str:
    """读取 ``browser/scripts/<name>``（``.js`` 后缀可省略），按名缓存。"""
    filename = name if name.endswith(".js") else f"{name}.js"
    return (_SCRIPTS_DIR / filename).read_text(encoding="utf-8")
