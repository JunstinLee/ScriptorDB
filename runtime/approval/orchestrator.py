from __future__ import annotations

"""审批编排器：拥有 agent run 的事件循环、审批/接管挂起唤醒、外部信号入口。

依赖均经构造注入（store / takeover controller），未注入时懒解析到
runtime.approval 模块级单例或默认浏览器实现。
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic_ai import DeferredToolResults, ToolApproved, ToolDenied
from pydantic_ai.messages import ModelMessage

from agents.app_context import AppContext
from config.app_config import AppConfig
from runtime.run_tracker import RunTracker, utc_now_iso
from runtime.runner.takeover_hook import RunPauseState
from runtime.sessions import SessionStore, get_session_store
from services.session_service import persist_cancelled_takeover
from runtime.approval.controller import TakeoverController, _BrowserTakeoverController
from runtime.approval.pause import ApprovalPauseState
from runtime.approval.resumable import run_agent_stream_resumable
from runtime.approval.store import (
    PendingApprovalStore,
    TakeoverCheckpointStore,
    get_pending_store,
    get_takeover_checkpoint_store,
)


class _LoopAction(Enum):
    """事件分发结果：继续当前流 / 重启流 / 结束 run。"""

    CONTINUE = 0
    RESTART = 1
    END = 2


@dataclass
class _RunState:
    """一次 run 的运行期状态（替代散落的局部变量与 out-param 收集器）。"""

    tracker: RunTracker
    agent: Any
    prompt: str
    history: list[ModelMessage]
    deferred_results: DeferredToolResults | None = None
    new_messages: list[ModelMessage] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.tracker.run_id,
            "status": self.tracker.status,
            "new_messages": self.new_messages,
            "final_output": self.tracker.final_output,
            "tool_invocations": self.tracker.tool_invocations,
            "started_at": self.tracker.started_at,
            "ended_at": self.tracker.ended_at,
        }


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
        pending_store: PendingApprovalStore | None = None,
        checkpoint_store: TakeoverCheckpointStore | None = None,
        session_store: SessionStore | None = None,
        takeover: TakeoverController | None = None,
    ):
        self.session_id = session_id
        self.config = config
        self.model = model
        self.provider = provider
        self.agent = agent
        self._app_context = app_context or AppContext(self.config)
        # 依赖注入：显式传入优先；未注入时在使用点懒解析到模块级单例，
        # 与原有全局状态一致（对测试 monkeypatch 时序零敏感）。
        self._pending_store = pending_store
        self._checkpoint_store = checkpoint_store
        self._session_store = session_store
        self._takeover = takeover or _BrowserTakeoverController()
        self._run_tracker: RunTracker | None = None
        # 接管暂停：hook 挂起在 resume_event.wait()，resume_takeover() set() 唤醒，
        # 取消/超时置 cancelled 后终止 run。审批暂停同模式，signal_approval() 唤醒。
        self._approval = ApprovalPauseState()
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
        self._approval = ApprovalPauseState()
        state = _RunState(
            tracker=self._run_tracker,
            agent=self.agent or self._resolve_agent(),
            prompt=prompt,
            history=list(message_history),
        )

        await self._run_loop(state, event_callback)

        return state.summary()

    async def _run_loop(
        self,
        state: _RunState,
        event_callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> bool:
        """Run the agent loop, pausing for approvals and resuming in-place.

        approval_request 时挂起在审批 resume_event 上（SSE 流保持打开，与接管
        同一模式），signal_approval() 唤醒后经 RESTART 重启流继续同一 run；
        run 完成（run_end）返回 True。
        """
        while True:
            async for event in run_agent_stream_resumable(
                state.prompt,
                state.history,
                self.config,
                model=self.model,
                provider=self.provider,
                agent=state.agent,
                tracker=state.tracker,
                deferred_results=state.deferred_results,
                pause=self._pause,
            ):
                action = await self._dispatch_event(event, state, event_callback)
                if action is _LoopAction.END:
                    return True
                if action is _LoopAction.RESTART:
                    break
            else:
                # async for 正常耗尽（run_end 已推送）：run 完成
                return True

    def _clear_checkpoint(self) -> None:
        """清理当前 session 的接管 checkpoint（终态必经：取消/超时/正常完成）。"""
        (self._checkpoint_store or get_takeover_checkpoint_store()).remove(self.session_id)

    async def _dispatch_event(
        self,
        event: dict[str, Any],
        state: _RunState,
        event_callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> _LoopAction:
        """分发单个 run 事件。分支语义不可互换：approval 唤醒后必须 RESTART
        （流已结束需重启）；human_takeover_request 必须 CONTINUE（hook 挂起在
        栈深处，流未结束）；takeover_cancelled / run_end 必须 END（终态）。"""
        ev_type = event.get("type")
        if ev_type == "new_messages":
            state.new_messages.extend(event.get("messages", []))
            return _LoopAction.CONTINUE
        if ev_type == "approval_request":
            return await self._handle_approval_request(event, state, event_callback)
        if ev_type == "human_takeover_request":
            # run 挂起在 hook 的 resume_event.wait() 上，不结束 run
            await event_callback(event)
            return _LoopAction.CONTINUE
        if ev_type == "takeover_cancelled":
            await event_callback(event)
            self._takeover.reset()
            # 超时/取消路径都要清掉 checkpoint，避免残留占用
            self._clear_checkpoint()
            return _LoopAction.END
        if ev_type == "run_end":
            await event_callback(event)
            self._takeover.reset()
            self._clear_checkpoint()
            return _LoopAction.END
        await event_callback(event)
        return _LoopAction.CONTINUE

    async def _handle_approval_request(
        self,
        event: dict[str, Any],
        state: _RunState,
        event_callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> _LoopAction:
        """审批请求：转发后挂起等待 /approve；唤醒后消费 pending 并重启流。

        signal_approval() 先写 decision 再 set()（顺序契约）；pending 在唤醒
        后才 pop，避免双点/过期请求提前消费。"""
        await event_callback(event)
        await self._approval.resume_event.wait()
        if self._approval.cancelled:
            # 审批被取消：记录取消终态，结束 run
            request_id = event.get("request_id", "")
            if request_id:
                (self._pending_store or get_pending_store()).pop(request_id)
            state.tracker.status = "cancelled"
            state.tracker.ended_at = utc_now_iso()
            await event_callback({"type": "metadata", **state.summary()})
            await event_callback({
                "type": "run_end",
                "run_id": state.tracker.run_id,
                "timestamp": utc_now_iso(),
            })
            return _LoopAction.END
        results = self._approval.decision
        request_id = event.get("request_id", "")
        pending = (self._pending_store or get_pending_store()).pop(request_id) if request_id else None
        if pending is not None:
            state.history = list(pending.message_history)
        state.deferred_results = results
        state.prompt = "Continue"
        self._approval = ApprovalPauseState()
        return _LoopAction.RESTART

    def _resolve_agent(self) -> Any:
        return self._app_context.resolve_agent(self.model, self.provider)

    def signal_approval(
        self,
        request_id: str,
        approved_map: dict[str, bool],
        override_args: dict | None = None,
    ) -> dict[str, Any]:
        """/approve 端点信号：校验 pending 后构建审批结果并唤醒挂起的 run。

        不重启 run、不开新 SSE 流；pending 由 _handle_approval_request 唤醒后
        按 request_id 消费（此处只读不弹）。后续事件继续由原 chat SSE 流推送。
        """
        pending = (self._pending_store or get_pending_store()).get(request_id)
        if pending is None:
            return {"ok": False, "error": "no_pending"}
        results = DeferredToolResults()
        if pending.auto_results is not None:
            results.approvals.update(pending.auto_results.approvals)
        for call in pending.deferred_calls:
            call_id = call["tool_call_id"]
            if approved_map.get(call_id, False):
                if override_args and call_id in override_args:
                    results.approvals[call_id] = ToolApproved(override_args=override_args[call_id])
                else:
                    results.approvals[call_id] = ToolApproved()
            else:
                results.approvals[call_id] = ToolDenied("User denied the operation.")
        self._approval.decision = results
        self._approval.resume_event.set()
        return {"ok": True, "run_id": self.run_id}

    def resume_takeover(self, run_id: str, takeover_result: str) -> dict[str, Any]:
        """从人工接管暂停中恢复当前 run，不重启 agent。

        校验 run_id 后设置 resume_event；hook 中的 wait() 立刻返回，
        原来的 tool call / agent 执行栈继续往下走。
        """
        if run_id and (self._run_tracker is None or self._run_tracker.run_id != run_id):
            return {"ok": False, "error": "run_mismatch"}
        if self._pause.cancelled:
            return {"ok": False, "error": "takeover_cancelled"}

        # complete 必须先于 set()：hook 唤醒后立刻读取接管结果
        self._takeover.complete(takeover_result)

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

        checkpoint = (self._checkpoint_store or get_takeover_checkpoint_store()).get(self.session_id)
        if checkpoint is None:
            return {"ok": False, "error": "no_active_takeover", "status": "not_cancelled"}

        # 终态落盘必须在唤醒挂起的 run 之前完成（顺序契约）
        persist_cancelled_takeover(
            self._session_store or get_session_store(), self.session_id, checkpoint
        )

        self._clear_checkpoint()

        self._takeover.cancel(reason or "用户取消接管")
        # 唤醒挂起的 run：hook 检测到 cancelled 后调用 ctx.cancel()，
        # pydantic-ai 停止 run 并抛 RunCancelled，lifecycle 转取消终态。
        self._pause.cancel_run()
        return {"ok": True, "status": "cancelled", "reason": reason or "用户取消接管"}
