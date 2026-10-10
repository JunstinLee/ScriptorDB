"""工具调用前的观测副作用：记录浏览器使用与 detect_filters 使用。

在任何策略判定之前执行，与策略是否拦截无关——观测结果供后续策略
（python 守卫、filter 管线）消费。
"""

from __future__ import annotations

from runtime.middleware import context as ctxmod
from runtime.middleware.state import STATE


def observe(ctx, tool_name: str) -> None:
    round_id = ctxmod._round_key(ctx)
    if ctxmod._is_browser_tool(tool_name):
        STATE.mark_browser_used(round_id)
    if tool_name == "browser_detect_filters":
        STATE.mark_detect_used(round_id)
