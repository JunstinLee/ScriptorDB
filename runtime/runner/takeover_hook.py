from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelRequest

from core.logging_setup import get_logger
from runtime.approval.store import PendingTakeover, get_takeover_checkpoint_store
from runtime.run_tracker import utc_now_iso
from runtime.runner.events import (
    browser_action_event,
    human_takeover_request_event,
    login_form_detected_event,
)

logger = get_logger("agent_runner.takeover")


class TakeoverCancelledError(Exception):
    """run 内信号：人工接管被取消/超时，终止本次 run。

    hook 调用 ctx.cancel() 后抛出；lifecycle 捕获后转为 takeover_cancelled
    终态事件。即使 pydantic-ai 对 event_stream_handler 的异常做包装，
    ctx.cancel() 触发的 RunCancelled 也会由 lifecycle 兜底捕获。
    """


@dataclass
class RunPauseState:
    """当前 run 的人工接管暂停状态。

    orchestrator 为每个活跃 run 持有一个实例：检测到接管后 hook 挂起在
    resume_event.wait()，恢复端点 set() 唤醒继续原执行栈；取消/超时则置
    cancelled 后唤醒，hook 转而调用 ctx.cancel() 终止本次 run。
    """

    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled: bool = False

    def cancel_run(self) -> None:
        """取消语义：唤醒挂起的 run，并标记为取消（而非恢复）。"""
        self.cancelled = True
        self.resume_event.set()


@dataclass
class AfterToolContext:
    """Everything the takeover hook needs to inspect/pause after a browser tool result."""

    queue: Any  # asyncio.Queue[dict]
    tool_name: str
    success: bool
    session_id: str
    run_id: str
    checkpoint_id: str
    prompt: str
    message_history: list[ModelMessage]
    tool_parts: list[Any]
    tool_invocations: list[dict[str, Any]]
    final_output: str
    ctx: Any = None  # RunContext：恢复时注入接管结果消息（取消走 TakeoverCancelledError）
    pause: RunPauseState | None = None


class BrowserTakeoverHook:
    """Cross-cutting browser human-takeover check after browser tool results.

    Injectable: the translator depends on this interface rather than on the
    browser package, so it can be unit-tested with a fake hook.
    """

    async def after_tool_result(self, ctx: AfterToolContext) -> None:
        if not ctx.tool_name.startswith("browser_"):
            return
        try:
            from browser import get_manager

            mgr = get_manager()
            state = await mgr.get_state()
            actions = state.get("actions", [])
            if actions:
                latest = actions[-1]
                await ctx.queue.put(browser_action_event(
                    run_id=ctx.run_id,
                    tool=latest.get("tool", ctx.tool_name),
                    selector=latest.get("selector", ""),
                    coords=latest.get("coords", {}),
                    success=latest.get("success", ctx.success),
                    detail=latest.get("detail", ""),
                    timestamp=latest.get("timestamp", utc_now_iso()),
                ))
            try:
                await mgr.detect_takeover()
            except Exception as e:
                logger.debug("takeover detection skipped: %s", e)
            # 登录页字段自动提取（旁路，非 AI 工具）：命中即发事件并注入对话，
            # 去重由 manager.detect_login_form 内部签名缓存保证。
            login_form: dict[str, Any] | None = None
            try:
                info = await mgr.detect_login_form()
            except Exception as e:
                logger.debug("login form detection skipped: %s", e)
                info = None
            if info is not None:
                login_form = info.to_dict()
                await ctx.queue.put(login_form_detected_event(
                    run_id=ctx.run_id,
                    login_form=login_form,
                    timestamp=utc_now_iso(),
                ))
                if ctx.ctx is not None:
                    try:
                        from browser.login_form import format_login_form_message
                        await ctx.ctx.enqueue(format_login_form_message(info))
                    except Exception as e:
                        logger.debug("enqueue login form info failed: %s", e)
            takeover = mgr.takeover if mgr else None
            if takeover and takeover.should_pause_agent():
                takeover.enter_waiting(
                    on_timeout=ctx.pause.cancel_run if ctx.pause else None
                )
                logger.warning(
                    "agent paused for takeover reason=%s trigger=%s",
                    takeover.reason, takeover.trigger,
                )
                checkpoint = PendingTakeover(
                    session_id=ctx.session_id,
                    run_id=ctx.run_id,
                    checkpoint_id=ctx.checkpoint_id,
                    prompt=ctx.prompt,
                    message_history=list(ctx.message_history),
                    turn_new_messages=(
                        [ModelRequest(parts=list(ctx.tool_parts))]
                        if ctx.tool_parts
                        else []
                    ),
                    tool_invocations=list(ctx.tool_invocations),
                    final_output=ctx.final_output,
                    reason=takeover.reason,
                    trigger=takeover.trigger,
                    created_at=utc_now_iso(),
                    login_form=login_form,
                )
                get_takeover_checkpoint_store().add(checkpoint)
                state_after = await mgr.get_state()
                await ctx.queue.put(human_takeover_request_event(
                    run_id=ctx.run_id,
                    checkpoint_id=ctx.checkpoint_id,
                    reason=takeover.reason,
                    trigger=takeover.trigger,
                    current_url=state_after.get("url", ""),
                    screenshot_available=state_after.get("screenshot_available", False),
                    login_form=login_form,
                    timestamp=utc_now_iso(),
                ))
                if ctx.pause is None:
                    # 无暂停状态（理论不出现）：仅通知前端，不挂起。
                    return
                # 挂起：agent.run() 的执行停在这里，等待恢复或取消。
                await ctx.pause.resume_event.wait()
                if ctx.pause.cancelled:
                    logger.warning(
                        "takeover cancelled during pause, cancelling run run_id=%s",
                        ctx.run_id,
                    )
                    # 单一取消通道：自定义异常终止 run（不依赖 pydantic-ai 版本差异）
                    raise TakeoverCancelledError(ctx.run_id)
                # 恢复：允许下一次挂起，并把用户操作结果注入对话。
                ctx.pause.resume_event.clear()
                result = takeover.result or ""
                logger.info("takeover resumed run_id=%s result=%s", ctx.run_id, result)
                if ctx.ctx is not None and result:
                    try:
                        await ctx.ctx.enqueue(f"用户完成了人工操作: {result}")
                    except Exception as e:
                        logger.debug("enqueue takeover result failed: %s", e)
        except Exception as e:
            if isinstance(e, TakeoverCancelledError):
                raise
            logger.debug("browser takeover check skipped: %s", e)
