from __future__ import annotations

"""可恢复的 agent 事件流：自动审批在内部循环续跑（迭代而非递归）。

包装 runtime.agent_runner.run_agent_stream，拦截 _deferred_tool_requests：
- 全部自动批准 → 注入审批结果后重启流继续；
- 需人工审批 → yield approval_request 后 return，由调用方挂起/唤醒后重启本流。
"""

from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolApproved
from pydantic_ai.messages import ModelMessage

from config.app_config import AppConfig
from runtime.agent_runner import run_agent_stream
from runtime.run_tracker import RunTracker
from runtime.runner.takeover_hook import RunPauseState
from runtime.approval.policy import _process_deferred_requests


async def run_agent_stream_resumable(
    prompt: str,
    message_history: list[ModelMessage],
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
    agent: Any | None = None,
    tracker: RunTracker | None = None,
    deferred_results: DeferredToolResults | None = None,
    pause: RunPauseState | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Stream agent events and handle deferred tool approval decisions.

    Yields run_start, run_end, error, metadata, tool_call, tool_result, text_delta,
    trace, takeover_cancelled, and approval_request events.

    自动审批在内部循环续跑（迭代而非递归）；需人工审批时 yield approval_request
    后 return，由调用方挂起/唤醒后重启本流。
    """
    local_tracker = tracker or RunTracker()
    current_prompt = prompt
    current_history = message_history
    results: DeferredToolResults | None = deferred_results
    while True:
        async for event in run_agent_stream(
            current_prompt,
            current_history,
            config,
            model=model,
            provider=provider,
            agent=agent,
            tracker=local_tracker,
            deferred_results=results,
            pause=pause,
        ):
            if event.get("type") == "_deferred_tool_requests":
                deferred: DeferredToolRequests = event["deferred"]
                # Use the full message history returned by the agent run so that
                # deferred tool calls are present when the run is resumed.
                all_messages = event.get("all_messages", current_history)
                approval_event = _process_deferred_requests(
                    event.get("session_id", ""),
                    local_tracker.run_id,
                    all_messages,
                    deferred,
                    tracker=local_tracker,
                )
                if approval_event:
                    yield approval_event
                    return  # Pause; caller will resume after POST /approve.
                # All requests auto-approved; continue the run with results.
                results = _auto_approve_all(deferred)
                current_prompt = "Continue"
                current_history = all_messages
                break
            yield event
        else:
            return


def _auto_approve_all(deferred: DeferredToolRequests) -> DeferredToolResults:
    results = DeferredToolResults()
    for call in deferred.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results
