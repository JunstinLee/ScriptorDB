"""策略注册表与调度：把原先一条长 if 链换成有序策略遍历。

顺序即优先级：筛选/UI-probe 最先（页面已有筛选组件时优先），其后是 python 守卫
（观测），再是 find 熔断、js 结构枚举、全页链接收集，最后是文档改派。任一策略返回
非 ``None`` 即短路；全部返回 ``None`` 则放行（fail-open）。
"""

from __future__ import annotations

from runtime.middleware.observe import observe
from runtime.middleware.policies import (
    DocumentSwitchPolicy,
    FilterPipelinePolicy,
    FindRepeatPolicy,
    JsStructureSwitchPolicy,
    LinkSwitchPolicy,
    PythonGuardPolicy,
)

# 顺序即优先级，勿随意调整（见模块文档）。
POLICIES = (
    FilterPipelinePolicy(),
    PythonGuardPolicy(),
    FindRepeatPolicy(),
    JsStructureSwitchPolicy(),
    LinkSwitchPolicy(),
    DocumentSwitchPolicy(),
)


async def evaluate_call(ctx, tool_name: str, args: dict | None = None) -> str:
    """Decide whether a tool call may execute.

    Returns one of:
    - "allow":      execute normally
    - "switch":     block and auto-switch to a more appropriate tool
    - "repeat":     block; same tool already blocked this round — do not run anything
    - "no-python":  block; browser control task forbids python_sandbox_execute
    - "filter-block"/"filter-repeat": block; page exposes an interactive filtering UI
    - "ui-probe-block"/"ui-probe-repeat": block; DOM/UI probing script on an interactive page
    - "find-repeat":  block; the same browser_find query already succeeded on this page state
    - "link-repeat":  block; the same browser_read link-collection call was already intercepted this round

    Fails open: any uncertainty → "allow".
    """
    if ctx is None or getattr(ctx, "deps", None) is None:
        return "allow"
    observe(ctx, tool_name)
    for policy in POLICIES:
        decision = await policy.evaluate(ctx, tool_name, args)
        if decision is not None:
            return decision
    return "allow"
