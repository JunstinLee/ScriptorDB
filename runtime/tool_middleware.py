"""向后兼容 shim：实现已拆分到 :mod:`runtime.middleware` 包。

- 判定：``runtime.middleware.registry.evaluate_call``（有序策略注册表）
- 处置：``runtime.middleware.switch.execute_switch``
- 状态：``runtime.middleware.state.STATE``
- 策略：``runtime.middleware.policies.*``

本模块只做 re-export，勿在此新增逻辑。
"""

from __future__ import annotations

from runtime.middleware import clear_run, evaluate_call, execute_switch, record_find
from runtime.middleware.context import (
    _content_revision,
    _find_fingerprint,
    _find_tool_func,
    _is_browser_tool,
    _manager,
    _nav_revision,
    _normalize_query_part,
    _page_key,
    _page_url,
    _round_key,
    _run_key,
)
from runtime.middleware.policies.find_repeat import _is_repeat_find
from runtime.middleware.state import _MAX_ROUNDS, STATE

# 旧测试直接清空这些容器；它们与 STATE 内的字典同身份。
_round_finds = STATE.finds
_round_blocks = STATE.blocks
_round_browser_used = STATE.browser_used
_round_detect_used = STATE.detect_used

__all__ = [
    "evaluate_call",
    "execute_switch",
    "record_find",
    "clear_run",
    "_is_repeat_find",
    "_find_fingerprint",
    "_normalize_query_part",
    "_round_key",
    "_run_key",
    "_manager",
    "_page_key",
    "_page_url",
    "_nav_revision",
    "_content_revision",
    "_is_browser_tool",
    "_find_tool_func",
    "_round_finds",
    "_round_blocks",
    "_round_browser_used",
    "_round_detect_used",
    "_MAX_ROUNDS",
]
