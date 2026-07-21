from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, ToolApproved, ToolDenied
from pydantic_ai.messages import ModelMessage

from agents.db_agent import get_agent
from config.app_config import AppConfig
from config.models import fuzzy_match_model
from server.agent_runner import run_agent_stream
from server.approval_policy import (
    HIGH_RISK_IMPORT_TOOLS,
    IMPORT_ROW_THRESHOLD,
    LOW_RISK_WRITE_TOOLS,
    PendingApproval,
    get_pending_store,
)
from server.import_inspector import count_import_rows
from server.run_tracker import RunTracker, utc_now_iso


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
        agent: Agent[AppConfig] | None = None,
    ):
        self.session_id = session_id
        self.config = config
        self.model = model
        self.provider = provider
        self.agent = agent
        self._run_tracker: RunTracker | None = None

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
        """Run one iteration. Returns True if the run completed, False if paused for approval."""
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
        ):
            ev_type = event.get("type")
            if ev_type == "new_messages":
                new_messages_collector.extend(event.get("messages", []))
                continue
            if ev_type == "approval_request":
                await event_callback(event)
                return False
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
        if self.provider:
            self.config.llm_provider = self.provider
        if self.model:
            matched = fuzzy_match_model(self.config.llm_provider, self.model)
            if matched:
                self.config.llm_model = matched
        return get_agent(self.config, self.model, self.provider)

    async def resume_with_approval(
        self,
        request_id: str,
        approved_map: dict[str, bool],
        event_callback: Callable[[dict[str, Any]], Awaitable[None]],
        run_collector: dict[str, Any],
        new_messages_collector: list[ModelMessage],
    ) -> bool:
        """Resume a previously paused run after the user approved/denied calls."""
        pending = get_pending_store().pop(request_id)
        if pending is None:
            return False

        if self._run_tracker is None:
            self._run_tracker = RunTracker(run_id=pending.run_id)

        print(f"[approval_orchestrator] resume: run_id={pending.run_id} deferred_calls={[c['tool_call_id'] for c in pending.deferred_calls]} approved_map={approved_map}")
        all_denied = all(not approved_map.get(call["tool_call_id"], False) for call in pending.deferred_calls)

        if all_denied:
            self._run_tracker = RunTracker(run_id=pending.run_id)
            denial_message = "用户拒绝并暂停流程。"
            self._run_tracker.final_output = denial_message
            await event_callback({
                "type": "text_delta",
                "run_id": self._run_tracker.run_id,
                "delta": denial_message,
            })
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
            print("[approval_orchestrator] all calls denied, skipping _run_loop")
            return True

        results = DeferredToolResults()
        for call in pending.deferred_calls:
            call_id = call["tool_call_id"]
            approved = approved_map.get(call_id, False)
            print(f"[approval_orchestrator] call_id={call_id} approved={approved}")
            if approved:
                results.approvals[call_id] = ToolApproved()
            else:
                results.approvals[call_id] = ToolDenied("User denied the import operation.")

        print(f"[approval_orchestrator] entering _run_loop with {len(results.approvals)} results")
        completed = await self._run_loop(
            "Continue",
            pending.message_history,
            event_callback,
            run_collector=run_collector,
            new_messages_collector=new_messages_collector,
            deferred_results=results,
        )

        return completed


async def run_agent_stream_resumable(
    prompt: str,
    message_history: list[ModelMessage],
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
    agent: Any | None = None,
    tracker: RunTracker | None = None,
    deferred_results: DeferredToolResults | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Stream agent events and handle deferred tool approval decisions.

    Yields run_start, run_end, error, metadata, tool_call, tool_result, text_delta,
    trace, and approval_request events.
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
            )
            if approval_event:
                print(f"[approval_orchestrator] yielding approval_request and PAUSING: request_id={approval_event['request_id']} run_id={approval_event['run_id']}")
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
            ):
                yield resumed_event
            return

        yield event


def _process_deferred_requests(
    session_id: str,
    run_id: str,
    message_history: list[ModelMessage],
    deferred: DeferredToolRequests,
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
                print(f"[approval_orchestrator] _process_deferred: PENDING call_id={call.tool_call_id} tool={tool_name} rows={row_count}")
                continue
            auto_calls.append(call)
            print(f"[approval_orchestrator] _process_deferred: AUTO (low rows) call_id={call.tool_call_id} tool={tool_name}")
            continue
        auto_calls.append(call)
        print(f"[approval_orchestrator] _process_deferred: AUTO (unknown tool) call_id={call.tool_call_id} tool={tool_name}")

    if pending_calls:
        request_id = uuid.uuid4().hex[:12]
        pending = PendingApproval(
            request_id=request_id,
            session_id=session_id,
            run_id=run_id,
            message_history=list(message_history),
            deferred_calls=pending_calls,
        )
        get_pending_store().add(request_id, pending)
        print(f"[approval_orchestrator] creating approval_request: request_id={request_id} run_id={run_id} pending_call_ids={[c['tool_call_id'] for c in pending_calls]}")

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
        print(f"[approval_orchestrator] _auto_approve_all: call_id={call.tool_call_id}")
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
