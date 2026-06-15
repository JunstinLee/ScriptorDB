from __future__ import annotations

from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, RunContext
from pydantic_ai.capabilities import HandleDeferredToolCalls
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from agents.capabilities import build_audit_hooks
from config.models import resolve_model
from config.secrets import SUPPORTED_PROVIDERS, get_api_key
from config.settings import Settings
from tools.toolsets import read_toolset, viz_toolset, write_toolset


def _auto_approve_handler(
    ctx: RunContext[Settings],
    requests: DeferredToolRequests,
) -> DeferredToolResults:
    from pydantic_ai import ToolApproved

    results = DeferredToolResults()
    for call in requests.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results


_agent: Agent[Settings] | None = None


def get_agent(model: str | None = None, provider: str | None = None) -> Agent[Settings]:
    global _agent
    if _agent is None or model is not None or provider is not None:
        active_provider = provider or Settings().llm_provider
        resolved_model = (
            resolve_model(active_provider, model) if model else Settings().resolved_model
        )

        audit_hooks = build_audit_hooks()
        approval = HandleDeferredToolCalls(handler=_auto_approve_handler)

        if active_provider in ("nim", "together"):
            api_key = get_api_key(active_provider)
            config = SUPPORTED_PROVIDERS[active_provider]
            model_name = resolved_model.split(":", 1)[-1]
            _agent = Agent(
                model=OpenAIChatModel(
                    model_name,
                    provider=OpenAIProvider(base_url=config.base_url, api_key=api_key),
                ),
                deps_type=Settings,
                toolsets=[read_toolset, write_toolset, viz_toolset],
                capabilities=[audit_hooks, approval],
            )
        else:
            _agent = Agent(
                model=resolved_model,
                deps_type=Settings,
                toolsets=[read_toolset, write_toolset, viz_toolset],
                capabilities=[audit_hooks, approval],
            )
    return _agent
