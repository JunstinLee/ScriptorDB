"""browser 控制任务下的 python_sandbox_execute 守卫。

当前行为是「观测 + 记日志」，不产生拦截决策（``evaluate`` 恒返回 ``None``）：
浏览器控制任务中 python_sandbox_execute 已被更上层的沙箱约束覆盖，这里只保留
可观测性。若未来需要在中间件层硬拦，返回 ``"no-python"`` / ``"no-python-repeat"``
即可——对应文案已备在 labels。
"""

from __future__ import annotations

from core.logging_setup import get_logger
from runtime.middleware import context as ctxmod
from runtime.middleware.state import STATE
from runtime.middleware_probe import _browser_launched

logger = get_logger("tool_middleware")


class PythonGuardPolicy:
    """观测 python_sandbox_execute 与浏览器控制的并发。"""

    name = "python-guard"

    async def evaluate(self, ctx, tool_name: str, args: dict | None) -> str | None:
        if tool_name != "python_sandbox_execute":
            return None
        round_id = ctxmod._round_key(ctx)
        if STATE.browser_was_used(round_id) or _browser_launched():
            logger.info(
                "tool middleware: blocking python_sandbox_execute — browser control active (round %s)",
                round_id,
            )
        return None
