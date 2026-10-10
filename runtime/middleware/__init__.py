"""工具中间件：判定（策略注册表）与改派处置分离。

旧入口 ``runtime.tool_middleware`` 仍可用（re-export shim）。
"""

from __future__ import annotations

from runtime.middleware.policies.find_repeat import clear_run, record_find
from runtime.middleware.registry import evaluate_call
from runtime.middleware.switch import execute_switch

__all__ = ["evaluate_call", "execute_switch", "record_find", "clear_run"]
