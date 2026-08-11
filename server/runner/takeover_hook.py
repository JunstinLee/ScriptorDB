from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelRequest

from core.logging_setup import get_logger
from server.approval_policy import PendingTakeover, get_takeover_checkpoint_store
from server.run_tracker import utc_now_iso
from server.runner.events import browser_action_event, human_takeover_request_event

logger = get_logger("agent_runner.takeover")


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
            takeover = mgr.takeover if mgr else None
            if takeover and takeover.should_pause_agent():
                takeover.enter_waiting()
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
                    timestamp=utc_now_iso(),
                ))
        except Exception as e:  # keep original swallow semantics; now observable
            logger.debug("browser takeover check skipped: %s", e)
