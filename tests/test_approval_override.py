"""计划 02：approval 分流 + override_args 回传的服务端快测（无浏览器、无网络）。

覆盖验收标准 3：
- `_process_deferred_requests` 将 `browser_apply_filter` 归入 pending_calls（其余工具不受影响）
- `signal_approval` 带 override_args → `ToolApproved(override_args=…)`（无 override_args 时与现状一致）
- all-denied → `ToolDenied` 走标准 deferred 续跑（不再特判终止）
- `_run_loop` 挂起等待审批、唤醒后同一流继续（接管同模式）
- `ApprovalSubmitRequest.override_args` 结构校验
"""

import asyncio

import pytest
from pydantic import ValidationError
from pydantic_ai import (
    DeferredToolRequests,
    DeferredToolResults,
    ToolApproved,
    ToolDenied,
)
from pydantic_ai.messages import ToolCallPart

from schemas.approval import ApprovalSubmitRequest
from runtime.approval.orchestrator import ApprovalOrchestrator, _RunState
from runtime.approval.policy import _process_deferred_requests
from runtime.approval.store import PendingApproval, get_pending_store
from runtime.run_tracker import RunTracker


@pytest.fixture(autouse=True)
def _clean_pending_store():
    yield
    get_pending_store()._pending.clear()


def _deferred(*calls: ToolCallPart) -> DeferredToolRequests:
    return DeferredToolRequests(approvals=list(calls))


def _apply_filter_call(call_id: str = "c1") -> ToolCallPart:
    return ToolCallPart(
        tool_name="browser_apply_filter",
        args={"action": "select", "target": "Status", "value": "Active"},
        tool_call_id=call_id,
    )


def _make_orchestrator(session_id: str = "s-test"):
    # config/app_context 仅需非 None：resume 流程不读取
    return ApprovalOrchestrator(
        session_id=session_id, config=object(), app_context=object()
    )


def _seed_pending(request_id: str, deferred_calls: list[dict], session_id: str = "s-test"):
    pending = PendingApproval(
        request_id=request_id,
        session_id=session_id,
        run_id="run1",
        message_history=[],
        deferred_calls=deferred_calls,
        tool_invocations=[],
    )
    get_pending_store().add(request_id, pending)
    return pending


# ---------- _process_deferred_requests 分流 ----------


async def test_apply_filter_goes_to_pending_calls():
    ev = _process_deferred_requests(
        "s1", "run1", [], _deferred(_apply_filter_call()), tracker=None
    )
    assert ev is not None and ev["type"] == "approval_request"
    call = ev["calls"][0]
    assert call["tool_call_id"] == "c1"
    assert call["tool_name"] == "browser_apply_filter"
    assert call["args"]["value"] == "Active"
    # import 专用键不得出现在筛选确认条目
    assert "row_count" not in call and "table_name" not in call


async def test_low_risk_write_still_auto_approved():
    d = _deferred(
        ToolCallPart(tool_name="write_csv", args={"path": "x.csv"}, tool_call_id="c2")
    )
    assert _process_deferred_requests("s1", "run1", [], d, tracker=None) is None


async def test_unknown_tool_still_auto_approved():
    d = _deferred(ToolCallPart(tool_name="some_other_tool", args={}, tool_call_id="c3"))
    assert _process_deferred_requests("s1", "run1", [], d, tracker=None) is None


async def test_mixed_calls_only_filter_is_pending():
    d = _deferred(
        _apply_filter_call("c1"),
        ToolCallPart(tool_name="execute_ddl", args={"sql": "x"}, tool_call_id="c4"),
    )
    ev = _process_deferred_requests("s1", "run1", [], d, tracker=None)
    assert ev is not None
    assert [c["tool_call_id"] for c in ev["calls"]] == ["c1"]


# ---------- signal_approval 构建审批结果 + _run_loop 挂起/唤醒 ----------


async def test_signal_approval_with_override_args_builds_toolapproved():
    _seed_pending(
        "req-override",
        [{"tool_call_id": "c1", "tool_name": "browser_apply_filter",
          "args": {"action": "select", "target": "Status", "value": "Active"}}],
    )
    orch = _make_orchestrator()
    result = orch.signal_approval(
        "req-override",
        {"c1": True},
        override_args={"c1": {"action": "select", "target": "Status", "value": "Inactive"}},
    )
    assert result["ok"] is True
    assert orch._approval.resume_event.is_set()
    approval = orch._approval.decision.approvals["c1"]
    assert isinstance(approval, ToolApproved)
    assert approval.override_args == {"action": "select", "target": "Status", "value": "Inactive"}


async def test_signal_approval_without_override_args_plain_toolapproved():
    _seed_pending(
        "req-plain",
        [{"tool_call_id": "c1", "tool_name": "browser_apply_filter",
          "args": {"action": "select", "target": "Status", "value": "Active"}}],
    )
    orch = _make_orchestrator()
    result = orch.signal_approval("req-plain", {"c1": True})
    assert result["ok"] is True
    approval = orch._approval.decision.approvals["c1"]
    assert isinstance(approval, ToolApproved)
    assert approval.override_args is None


async def test_signal_approval_all_denied_builds_tooldenied():
    _seed_pending(
        "req-denied",
        [
            {"tool_call_id": "c1", "tool_name": "browser_apply_filter",
             "args": {"action": "select", "target": "Status", "value": "Active"}},
            {"tool_call_id": "c2", "tool_name": "browser_apply_filter",
             "args": {"action": "input", "target": "Query", "value": "x"}},
        ],
    )
    orch = _make_orchestrator()
    result = orch.signal_approval("req-denied", {"c1": False, "c2": False})
    assert result["ok"] is True
    decision = orch._approval.decision
    assert isinstance(decision.approvals["c1"], ToolDenied)
    assert isinstance(decision.approvals["c2"], ToolDenied)


async def test_signal_approval_unknown_request_id_fails():
    orch = _make_orchestrator()
    result = orch.signal_approval("req-missing", {"c1": True})
    assert result["ok"] is False
    assert result["error"] == "no_pending"
    assert orch._approval.resume_event.is_set() is False


async def test_run_loop_waits_for_approval_then_resumes(monkeypatch):
    """approval_request 后 _run_loop 挂起等待；signal_approval() 唤醒后
    以审批结果继续同一 run（不结束 run、事件走同一 callback）。"""
    orch = _make_orchestrator()
    monkeypatch.setattr(ApprovalOrchestrator, "_resolve_agent", lambda self: None)
    _seed_pending(
        "req-wait",
        [{"tool_call_id": "c1", "tool_name": "browser_apply_filter", "args": {}}],
    )
    events: list[dict] = []

    async def cb(event):
        events.append(event)

    async def fake_resumable(prompt, message_history, config, model=None, provider=None,
                             agent=None, tracker=None, deferred_results=None, pause=None):
        if deferred_results is None:
            yield {"type": "approval_request", "run_id": "run1",
                   "request_id": "req-wait", "calls": []}
        else:
            yield {"type": "run_end", "run_id": "run1", "timestamp": "t"}

    monkeypatch.setattr(
        "runtime.approval.orchestrator.run_agent_stream_resumable", fake_resumable
    )

    async def signal_later():
        await asyncio.sleep(0.01)
        return orch.signal_approval("req-wait", {"c1": True})

    signal_task = asyncio.create_task(signal_later())
    orch._run_tracker = RunTracker()
    state = _RunState(
        tracker=orch._run_tracker, agent=None, prompt="原始 prompt", history=[]
    )
    done = await orch._run_loop(state, cb)
    signaled = await signal_task
    assert done is True
    assert signaled["ok"] is True
    # 唤醒后同一 callback 收到后续 run_end；事件顺序：approval_request → run_end
    assert [e["type"] for e in events] == ["approval_request", "run_end"]
    # pending 在唤醒后被消费
    assert get_pending_store().get("req-wait") is None


# ---------- ApprovalSubmitRequest 结构 ----------


def test_approval_submit_request_override_args_shape():
    r = ApprovalSubmitRequest(
        request_id="r", approved_map={"c": True},
        override_args={"c": {"action": "select", "target": "Status"}},
    )
    assert r.override_args == {"c": {"action": "select", "target": "Status"}}


def test_approval_submit_request_override_args_defaults_empty():
    r = ApprovalSubmitRequest(request_id="r", approved_map={"c": True})
    assert r.override_args == {}


def test_approval_submit_request_rejects_non_dict_override():
    with pytest.raises(ValidationError):
        ApprovalSubmitRequest(
            request_id="r", approved_map={"c": True},
            override_args={"c": "not-a-dict"},
        )


# ---------- ToolApproved(override_args) 端到端生效（FunctionModel 驱动） ----------


async def test_override_args_reach_tool_via_deferred_results():
    """FunctionModel 驱动 agent.run：requires_approval 工具经
    deferred_tool_results={call_id: ToolApproved(override_args=用户值)} 续跑后，
    工具函数实际收到覆盖后的参数（用户值），而非原 args。"""
    from pydantic_ai import Agent, ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    received: dict[str, object] = {}
    turns = {"n": 0}

    def f_model(messages, info):
        turns["n"] += 1
        if turns["n"] == 1:
            # 第一轮：模型调用 deferred 工具 → agent 拦截，run 以 DeferredToolRequests 结束
            return ModelResponse(parts=[
                ToolCallPart(tool_name="greet", args={"name": "原值"}, tool_call_id="c1")
            ])
        return ModelResponse(parts=[TextPart(content="done")])

    agent = Agent(
        FunctionModel(f_model),
        name="approval_test_agent",
        output_type=[str, DeferredToolRequests],
    )

    @agent.tool_plain(requires_approval=True)
    def greet(name: str) -> str:
        received["name"] = name
        return f"hello {name}"

    result = await agent.run("调用 greet")
    assert isinstance(result.output, DeferredToolRequests)
    assert result.output.approvals[0].tool_call_id == "c1"
    assert received == {}  # 工具未执行（stop-the-world）

    resumed = await agent.run(
        "继续",
        message_history=result.all_messages(),
        deferred_tool_results=DeferredToolResults(approvals={
            "c1": ToolApproved(override_args={"name": "用户值"}),
        }),
    )
    assert resumed.output == "done"
    assert received == {"name": "用户值"}  # 覆盖参数生效，非原值
