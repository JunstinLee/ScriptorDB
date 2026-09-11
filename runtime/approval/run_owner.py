from __future__ import annotations

"""run 的 owner 协程：持有 run 生存期、终态落盘与注销。

run 不再由 SSE 响应生成器持有——订阅者（`/chat` 或 `GET /sessions/{id}/stream`）
断开只影响自己的连接，owner 继续等待 run 自身终态，随后落盘并从注册表注销。

槽位与承载 task 由 `api/routes/chat.py:chat()` 在同一段无 await 的同步代码里
构造并注册（含 409 检查），本模块不 register、不创建 task。
"""

import asyncio
from contextlib import suppress
from typing import Any

from pydantic_ai.messages import ModelMessage

from core.logging_setup import get_logger
from runtime.approval.run_registry import ActiveRun, get_run_registry
from services.chat_service import persist_chat_run

logger = get_logger("approval.run_owner")


def _should_persist(summary: dict[str, Any]) -> bool:
    return (
        summary["status"] == "completed"
        or summary.get("error_type") == "site_unavailable"
    )


async def execute_run(
    *,
    slot: ActiveRun,
    prompt: str,
    message_history: list[ModelMessage],
) -> None:
    """等待 run 终态、落盘、注销槽位；关闭/取消时不留下注册表残留。"""
    registry = get_run_registry()
    try:
        summary = await slot.orchestrator.start_run(
            prompt, message_history, slot.bus.publish
        )
        logger.info(
            "chat_run_finished session_id=%s status=%s run_id=%s",
            slot.session_id, summary["status"], summary["run_id"],
        )
        if _should_persist(summary):
            # new_messages 由 orchestrator 在 _dispatch_event 累积，不再经 SSE 侧收集
            persist_chat_run(
                session_id=slot.session_id,
                new_messages_collector=list(summary.get("new_messages", [])),
                run_collector=summary,
            )
            from browser import get_manager

            get_manager().schedule_idle_close()
        else:
            logger.warning(
                "chat_run_finished: status=%s not persisted session_id=%s",
                summary["status"], slot.session_id,
            )
    except asyncio.CancelledError:
        # 进程关闭：task 已取消（本协程即承载者），把挂起的暂停态收敛为终态
        try:
            outcome = slot.orchestrator.abort_paused_run("run cancelled")
            logger.warning(
                "chat_run_cancelled session_id=%s run_id=%s outcome=%s",
                slot.session_id, slot.run_id, outcome,
            )
        except Exception:
            logger.exception("chat_run_abort_failed session_id=%s", slot.session_id)
        raise
    finally:
        # 取消路径下 await 必须被保护，否则二次取消会打断清理，留下注册表残留
        with suppress(asyncio.CancelledError):
            await slot.bus.close()
        registry.remove(slot.session_id, slot.run_id)
