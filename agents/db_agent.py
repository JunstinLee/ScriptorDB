from __future__ import annotations

from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, RunContext
from pydantic_ai.capabilities import HandleDeferredToolCalls
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from agents.capabilities import build_audit_hooks
from config.app_config import AppConfig
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


def _build_agent(config: AppConfig, resolved_model: str) -> Agent[Settings]:
    audit_hooks = build_audit_hooks()
    approval = HandleDeferredToolCalls(handler=_auto_approve_handler)

    active_provider = config.llm_provider
    if active_provider in ("nim", "together"):
        api_key = get_api_key(active_provider, config.workspace_id)
        provider_cfg = SUPPORTED_PROVIDERS[active_provider]
        model_name = resolved_model.split(":", 1)[-1]
        return Agent(
            model=OpenAIChatModel(
                model_name,
                provider=OpenAIProvider(base_url=provider_cfg.base_url, api_key=api_key),
            ),
            deps_type=Settings,
            toolsets=[read_toolset, write_toolset, viz_toolset],
            capabilities=[audit_hooks, approval],
        )

    return Agent(
        model=resolved_model,
        deps_type=Settings,
        toolsets=[read_toolset, write_toolset, viz_toolset],
        capabilities=[audit_hooks, approval],
    )


def get_agent(
    model: str | None = None,
    provider: str | None = None,
    config: AppConfig | None = None,
) -> Agent[Settings]:
    if config is None:
        from config.settings import settings as _settings

        config = _settings
    active_provider = provider or config.llm_provider
    resolved = (
        resolve_model(active_provider, model) if model else config.resolved_model
    )
    return _build_agent(config, resolved)


def reset_agent_cache() -> None:
    """向后兼容：缓存现已绑定到 AppContext，无模块级缓存可清空。"""
    return None
