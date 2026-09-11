"""ToolApproved(override_args) 端到端生效（FunctionModel 驱动）。"""

from __future__ import annotations

from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolApproved


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
