from __future__ import annotations

from pydantic_ai import Agent, DeferredToolRequests

from agents.capabilities import build_audit_hooks, build_undo_hooks
from config.app_config import AppConfig
from config.models import resolve_model
from config.provider_adapter import build_model
from config.settings import Settings
from logging_setup import get_logger
from tools.toolsets import read_toolset, viz_toolset, write_toolset


_log = get_logger("agents.db_agent")


def _build_agent(config: AppConfig, resolved_model: str) -> Agent[Settings, str | DeferredToolRequests]:
    audit_hooks = build_audit_hooks()
    undo_hooks = build_undo_hooks()

    active_provider = config.llm_provider
    model = build_model(active_provider, resolved_model, config.workspace_id)

    _log.info(
        "build_agent: provider=%s model=%s toolsets=3",
        active_provider,
        resolved_model,
    )
    return Agent(
        model=model,
        deps_type=Settings,
        output_type=[str, DeferredToolRequests],
        toolsets=[read_toolset, write_toolset, viz_toolset],
        capabilities=[audit_hooks, undo_hooks],
    )


def get_agent(
    model: str | None = None,
    provider: str | None = None,
    config: AppConfig | None = None,
) -> Agent[Settings, str | DeferredToolRequests]:
    if config is None:
        from config.settings import settings as _settings

        config = _settings
    active_provider = provider or config.llm_provider
    resolved = (
        resolve_model(active_provider, model) if model else config.resolved_model
    )
    _log.info(
        "get_agent: requested_model=%s provider=%s resolved=%s",
        model,
        active_provider,
        resolved,
    )
    return _build_agent(config, resolved)


def reset_agent_cache() -> None:
    """向后兼容：缓存现已绑定到 AppContext，无模块级缓存可清空。"""
    return None
