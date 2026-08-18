from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, ToolApproved, ToolDenied
from pydantic_ai.messages import ModelMessage

from agents.app_context import AppContext
from config.app_config import AppConfig
from runtime.agent_runner import run_agent_stream
from runtime.approval_policy import (
    HIGH_RISK_IMPORT_TOOLS,
    HUMAN_APPROVAL_TOOLS,
    IMPORT_ROW_THRESHOLD,
    LOW_RISK_WRITE_TOOLS,
    PendingApproval,
    get_pending_store,
    get_takeover_checkpoint_store,
)
from runtime.import_inspector import count_import_rows
from runtime.run_tracker import RunTracker, utc_now_iso
from runtime.runner.takeover_hook import RunPauseState
from schemas import StoredRun, StoredToolInvocation
from runtime.sessions import get_session_store


class ApprovalOrchestrator:
    """Owns agent runs with conditional automatic approval of deferred tool calls.

    - Low-risk writes are approved automatically.
    - High-risk imports (row count > threshold) require human confirmation via SSE.
    """

    def __init__(
        self,
        session_id: str,
        config: AppConfig,
        model: str | None = None,
        provider: str | None = None,
        agent: Any | None = None,
        app_context: AppContext | None = None,
    ):
        self.session_id = session_id
        self.config = config
        self.model = model
        self.provider = provider
        self.agent = agent
        self._app_context = app_context or AppContext(self.config)
        self._run_tracker: RunTracker | None = None
        # 人工接管暂停状态：hook 挂起在 resume_event.wait()，
        # resume_takeover() set() 唤醒，取消/超时置 cancelled 后终止 run。
        self._pause = RunPauseState()

    @property
    def run_id(self) -> str:
        return self._run_tracker.run_id if self._run_tracker else ""

    async def start_run(
        self,
        prompt: str,
        message_history: list[ModelMessage],
        event_callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> dict[str, Any]:
        """Start a run and process deferred tool approvals until completion or pause.

        Returns a run summary dict.
        """
        self._run_tracker = RunTracker()
        self._pause = RunPauseState()
        run_collector: dict[str, Any] = {}
        new_messages_collector: list[ModelMessage] = []

        await self._run_loop(
            prompt,
            message_history,
            event_callback,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
        )

        return {
            "run_id": self._run_tracker.run_id,
            "status": self._run_tracker.status,
            "new_messages": new_messages_collector,
            "final_output": self._run_tracker.final_output,
            "tool_invocations": self._run_tracker.tool_invocations,
            "started_at": self._run_tracker.started_at,
            "ended_at": self._run_tracker.ended_at,
        }

    async def _run_loop(
        self,
        prompt: str,
        message_history: list[ModelMessage],
        event_callback: Callable[[dict[str, Any]], Awaitable[None]],
        run_collector: dict[str, Any],
        new_messages_collector: list[ModelMessage],
        deferred_results: DeferredToolResults | None = None,
    ) -> bool:
        """Run one iteration. Returns True if the run completed, False if paused for approval/takeover."""
        if self._run_tracker is None:
            self._run_tracker = RunTracker()
        agent = self.agent or self._resolve_agent()

        async for event in run_agent_stream_resumable(
            prompt,
            message_history,
            self.config,
            model=self.model,
            provider=self.provider,
            agent=agent,
            tracker=self._run_tracker,
            deferred_results=deferred_results,
            pause=self._pause,
        ):
            ev_type = event.get("type")
            if ev_type == "new_messages":
                new_messages_collector.extend(event.get("messages", []))
                continue
            if ev_type == "approval_request":
                await event_callback(event)
                return False
            if ev_type == "human_takeover_request":
                # 人工接管：run 挂起在 hook 的 resume_event.wait() 上，
                # 不结束 run；恢复后本循环继续消费后续事件。
                await event_callback(event)
                continue
            if ev_type == "takeover_cancelled":
                # 终止语义：取消只记录终态，不再静默启动后台模型回合。
                await event_callback(event)
                from browser import get_manager
                get_manager().takeover.reset()
                # 超时/取消路径都要清掉 checkpoint，避免残留占用
                get_takeover_checkpoint_store().remove(self.session_id)
                return True
            if ev_type == "run_end":
                await event_callback(event)
                from browser import get_manager
                get_manager().takeover.reset()
                return True
            if ev_type == "metadata":
                run_collector.update({
                    "run_id": self._run_tracker.run_id,
                    "status": self._run_tracker.status,
                    "final_output": self._run_tracker.final_output,
                    "tool_invocations": self._run_tracker.tool_invocations,
                    "started_at": self._run_tracker.started_at,
                    "ended_at": self._run_tracker.ended_at,
                })
            await event_callback(event)

        return True

    def _resolve_agent(self) -> Any:
        return self._app_context.resolve_agent(self.model, self.provider)

    async def resume_with_approval(
        self,
        request_id: str,
        approved_map: dict[str, bool],
        event_callback: Callable[[dict[str, Any]], Awaitable[None]],
        run_collector: dict[str, Any],
        new_messages_collector: list[ModelMessage],
        override_args: dict | None = None,
    ) -> bool:
        """Resume a previously paused run after the user approved/denied calls.

        override_args: call_id -> 用户修改后的最终参数（仅含被改字段）。
        未提供或缺失该 call_id 时按原参数执行（与现状一致）。
        """
        pending = get_pending_store().pop(request_id)
        if pending is None:
            return False

        if self._run_tracker is None:
            self._run_tracker = RunTracker(run_id=pending.run_id)
            self._run_tracker.tool_invocations = list(pending.tool_invocations)

        all_denied = all(not approved_map.get(call["tool_call_id"], False) for call in pending.deferred_calls)

        if all_denied:
            for call in pending.deferred_calls:
                self._run_tracker.add_tool_invocation(
                    call["tool_call_id"], call["tool_name"], call["args"]
                )
                self._run_tracker.complete_tool(
                    call["tool_call_id"],
                    False,
                    "User cancelled the operation",
                    None,
                    None,
                )
            self._run_tracker.finish()
            run_collector.update({
                "run_id": self._run_tracker.run_id,
                "status": self._run_tracker.status,
                "final_output": self._run_tracker.final_output,
                "tool_invocations": self._run_tracker.tool_invocations,
                "started_at": self._run_tracker.started_at,
                "ended_at": self._run_tracker.ended_at,
            })
            await event_callback({
                "type": "metadata",
                "run_id": self._run_tracker.run_id,
                "status": self._run_tracker.status,
                "final_output": self._run_tracker.final_output,
                "tool_invocations": self._run_tracker.tool_invocations,
                "started_at": self._run_tracker.started_at,
                "ended_at": self._run_tracker.ended_at,
            })
            await event_callback({
                "type": "run_end",
                "run_id": self._run_tracker.run_id,
                "timestamp": utc_now_iso(),
            })
            session = get_session_store().get(self.session_id)
            if session is not None:
                run = StoredRun(
                    run_id=run_collector["run_id"],
                    status=run_collector["status"],
                    tool_invocations=[
                        StoredToolInvocation(**inv)
                        for inv in run_collector.get("tool_invocations", [])
                    ],
                    final_output=run_collector.get("final_output", ""),
                    started_at=run_collector["started_at"],
                    ended_at=run_collector.get("ended_at"),
                )
                session.add_run(run)
                get_session_store().save()
            return True

        results = DeferredToolResults()
        denied_ids = []
        for call in pending.deferred_calls:
            call_id = call["tool_call_id"]
            approved = approved_map.get(call_id, False)
            if approved:
                if override_args and call_id in override_args:
                    results.approvals[call_id] = ToolApproved(override_args=override_args[call_id])
                else:
                    results.approvals[call_id] = ToolApproved()
            else:
                denied_ids.append(call_id)
                self._run_tracker.add_tool_invocation(
                    call_id, call["tool_name"], call["args"]
                )
                results.approvals[call_id] = ToolDenied("User denied the import operation.")
        completed = await self._run_loop(
            "Continue",
            pending.message_history,
            event_callback,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
            deferred_results=results,
        )

        return completed

    def resume_takeover(self, run_id: str, takeover_result: str) -> dict[str, Any]:
        """从人工接管暂停中恢复当前 run，不重启 agent。

        校验 run_id 后设置 resume_event；hook 中的 wait() 立刻返回，
        原来的 tool call / agent 执行栈继续往下走。返回 {"ok": True, ...}。
        """
        if run_id and (self._run_tracker is None or self._run_tracker.run_id != run_id):
            return {"ok": False, "error": "run_mismatch"}
        if self._pause.cancelled:
            return {"ok": False, "error": "takeover_cancelled"}

        from browser import get_manager
        mgr = get_manager()
        mgr.takeover.complete(takeover_result)
        mgr.clear_auth_challenge()

        self._pause.resume_event.set()
        return {"ok": True, "status": "resumed", "run_id": self.run_id}

    def cancel_takeover(self, run_id: str = "", reason: str = "") -> dict[str, Any]:
        """Cancel the active takeover with terminate semantics.

        Validates the run_id against the orchestrator's active run, persists a
        clear terminal state (checkpoint messages + cancelled run), then clears
        the orchestrator-level takeover state. Caller is responsible for
        removing the orchestrator from the active registry.
        """
        if run_id and (self._run_tracker is None or self._run_tracker.run_id != run_id):
            return {"ok": False, "error": "run_mismatch", "status": "not_cancelled"}

        checkpoint = get_takeover_checkpoint_store().get(self.session_id)
        if checkpoint is None:
            return {"ok": False, "error": "no_active_takeover", "status": "not_cancelled"}

        session = get_session_store().get(self.session_id)
        if session is not None:
            if checkpoint.turn_new_messages:
                session.add_model_messages(list(checkpoint.turn_new_messages))
            run = StoredRun(
                run_id=checkpoint.run_id,
                status="cancelled",
                tool_invocations=[
                    StoredToolInvocation(**inv)
                    for inv in checkpoint.tool_invocations
                ],
                final_output=checkpoint.final_output,
                started_at=checkpoint.created_at,
                ended_at=utc_now_iso(),
            )
            session.add_run(run)
            get_session_store().save()

        get_takeover_checkpoint_store().remove(self.session_id)

        from browser import get_manager
        mgr = get_manager()
        mgr.takeover.cancel(reason or "用户取消接管")
        mgr.clear_auth_challenge()
        # 唤醒挂起的 run：hook 检测到 cancelled 后调用 ctx.cancel()，
        # pydantic-ai 停止 run 并抛 RunCancelled，lifecycle 转取消终态。
        self._pause.cancel_run()
        return {"ok": True, "status": "cancelled", "reason": reason or "用户取消接管"}


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
    """
    local_tracker = tracker or RunTracker()

    async for event in run_agent_stream(
        prompt,
        message_history,
        config,
        model=model,
        provider=provider,
        agent=agent,
        tracker=local_tracker,
        deferred_results=deferred_results,
        pause=pause,
    ):
        ev_type = event.get("type")
        if ev_type == "metadata":
            # The underlying runner may emit metadata; we keep it for run_end.
            yield event
            continue
        if ev_type == "run_end":
            yield event
            continue
        if ev_type == "error":
            yield event
            continue
        if ev_type == "new_messages":
            # Buffer and only emit at the end, or pass through for collection.
            yield event
            continue

        # Intercept completion with DeferredToolRequests.
        if ev_type == "_deferred_tool_requests":
            deferred: DeferredToolRequests = event["deferred"]
            session_id = event.get("session_id", "")
            # Use the full message history returned by the agent run so that
            # deferred tool calls are present when the run is resumed.
            all_messages = event.get("all_messages", message_history)
            approval_event = _process_deferred_requests(
                session_id,
                local_tracker.run_id,
                all_messages,
                deferred,
                tracker=local_tracker,
            )
            if approval_event:
                yield approval_event
                # Pause; caller will resume after POST /approve.
                return
            # All requests auto-approved; continue the run with results.
            results = _auto_approve_all(deferred)
            async for resumed_event in run_agent_stream_resumable(
                "Continue",
                event.get("all_messages", message_history),
                config,
                model=model,
                provider=provider,
                agent=agent,
                tracker=local_tracker,
                deferred_results=results,
                pause=pause,
            ):
                yield resumed_event
            return

        yield event


def _process_deferred_requests(
    session_id: str,
    run_id: str,
    message_history: list[ModelMessage],
    deferred: DeferredToolRequests,
    tracker: RunTracker | None = None,
) -> dict[str, Any] | None:
    """Split deferred calls into auto-approved and human-approval groups.

    Returns an approval_request event if any calls require human confirmation.
    """
    auto_calls: list[Any] = []
    pending_calls: list[dict[str, Any]] = []

    for call in deferred.approvals:
        tool_name = call.tool_name
        args = call.args_as_dict() if hasattr(call, "args_as_dict") else {}
        if tool_name in LOW_RISK_WRITE_TOOLS:
            auto_calls.append(call)
            continue
        if tool_name in HIGH_RISK_IMPORT_TOOLS:
            filepath = args.get("filepath", "") if isinstance(args, dict) else ""
            row_count = count_import_rows(filepath) if filepath else None
            if row_count is not None and row_count > IMPORT_ROW_THRESHOLD:
                pending_calls.append({
                    "tool_call_id": call.tool_call_id,
                    "tool_name": tool_name,
                    "args": args,
                    "row_count": row_count,
                    "table_name": args.get("table_name", "") if isinstance(args, dict) else "",
                })
                continue
            auto_calls.append(call)
            continue
        if tool_name in HUMAN_APPROVAL_TOOLS:
            pending_calls.append({
                "tool_call_id": call.tool_call_id,
                "tool_name": tool_name,
                "args": args,
            })
            continue
        auto_calls.append(call)

    if pending_calls:
        request_id = uuid.uuid4().hex[:12]
        pending = PendingApproval(
            request_id=request_id,
            session_id=session_id,
            run_id=run_id,
            message_history=list(message_history),
            deferred_calls=pending_calls,
            tool_invocations=list(tracker.tool_invocations) if tracker else [],
        )
        get_pending_store().add(request_id, pending)

        return {
            "type": "approval_request",
            "run_id": run_id,
            "request_id": request_id,
            "calls": pending_calls,
        }

    return None


def _auto_approve_all(deferred: DeferredToolRequests) -> DeferredToolResults:
    results = DeferredToolResults()
    for call in deferred.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results


async def submit_approval(
    request_id: str,
    approved_map: dict[str, bool],
) -> PendingApproval | None:
    """Used by the approval endpoint to signal user decisions.

    The actual resume happens in ApprovalOrchestrator.resume_with_approval.
    """
    pending = get_pending_store().get(request_id)
    if pending is None:
        return None
    pending.approved_map = approved_map
    return pending
