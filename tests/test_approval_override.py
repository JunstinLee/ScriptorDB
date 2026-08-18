"""计划 02：approval 分流 + override_args 回传的服务端快测（无浏览器、无网络）。

覆盖验收标准 3：
- `_process_deferred_requests` 将 `browser_apply_filter` 归入 pending_calls（其余工具不受影响）
- `resume_with_approval` 带 override_args → `ToolApproved(override_args=…)`（无 override_args 时与现状一致）
- all_denied 分支回归
- `ApprovalSubmitRequest.override_args` 结构校验
"""

import pytest
from pydantic import ValidationError
from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolApproved
from pydantic_ai.messages import ToolCallPart

from schemas.approval import ApprovalSubmitRequest
from runtime.approval_orchestrator import ApprovalOrchestrator, _process_deferred_requests
from runtime.approval_policy import PendingApproval, get_pending_store


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


# ---------- resume_with_approval override_args ----------


async def test_resume_with_override_args_builds_toolapproved(monkeypatch):
    _seed_pending(
        "req-override",
        [{"tool_call_id": "c1", "tool_name": "browser_apply_filter",
          "args": {"action": "select", "target": "Status", "value": "Active"}}],
    )
    captured: dict = {}

    async def fake_run_loop(self, prompt, message_history, event_callback,
                            run_collector, new_messages_collector, deferred_results=None):
        captured["results"] = deferred_results
        return True

    monkeypatch.setattr(ApprovalOrchestrator, "_run_loop", fake_run_loop)

    events: list[dict] = []

    async def cb(event):
        events.append(event)

    orch = _make_orchestrator()
    completed = await orch.resume_with_approval(
        "req-override",
        {"c1": True},
        cb,
        run_collector={},
        new_messages_collector=[],
        override_args={"c1": {"action": "select", "target": "Status", "value": "Inactive"}},
    )
    assert completed is True
    results = captured["results"]
    assert isinstance(results, DeferredToolResults)
    approval = results.approvals["c1"]
    assert isinstance(approval, ToolApproved)
    assert approval.override_args == {"action": "select", "target": "Status", "value": "Inactive"}


async def test_resume_without_override_args_plain_toolapproved(monkeypatch):
    _seed_pending(
        "req-plain",
        [{"tool_call_id": "c1", "tool_name": "browser_apply_filter",
          "args": {"action": "select", "target": "Status", "value": "Active"}}],
    )
    captured: dict = {}

    async def fake_run_loop(self, prompt, message_history, event_callback,
                            run_collector, new_messages_collector, deferred_results=None):
        captured["results"] = deferred_results
        return True

    monkeypatch.setattr(ApprovalOrchestrator, "_run_loop", fake_run_loop)

    async def cb(event):
        pass

    orch = _make_orchestrator()
    completed = await orch.resume_with_approval(
        "req-plain", {"c1": True}, cb, run_collector={}, new_messages_collector=[]
    )
    assert completed is True
    approval = captured["results"].approvals["c1"]
    assert isinstance(approval, ToolApproved)
    assert approval.override_args is None


async def test_resume_all_denied_terminates_run(monkeypatch):
    _seed_pending(
        "req-denied",
        [
            {"tool_call_id": "c1", "tool_name": "browser_apply_filter",
             "args": {"action": "select", "target": "Status", "value": "Active"}},
            {"tool_call_id": "c2", "tool_name": "browser_apply_filter",
             "args": {"action": "input", "target": "Query", "value": "x"}},
        ],
    )
    run_loop_called = False

    async def fake_run_loop(self, *args, **kwargs):
        nonlocal run_loop_called
        run_loop_called = True
        return True

    monkeypatch.setattr(ApprovalOrchestrator, "_run_loop", fake_run_loop)

    events: list[dict] = []

    async def cb(event):
        events.append(event)

    run_collector: dict = {}
    orch = _make_orchestrator()
    completed = await orch.resume_with_approval(
        "req-denied", {"c1": False, "c2": False}, cb,
        run_collector=run_collector,
        new_messages_collector=[],
    )
    assert completed is True
    assert run_loop_called is False
    assert any(e["type"] == "run_end" for e in events)
    assert any(e["type"] == "metadata" for e in events)
    # 工具以失败终态记录，不残留 pending
    invocations = run_collector.get("tool_invocations", [])
    assert len(invocations) == 2
    assert all(inv["status"] == "error" for inv in invocations)


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
