from __future__ import annotations

from pydantic_ai import Agent, DeferredToolRequests

from agents.capabilities import build_audit_hooks, build_undo_hooks
from config.app_config import AppConfig
from config.models import resolve_model
from config.provider_adapter import build_model
from config.settings import Settings
from tools.registry import get_all_tools
from tools.toolsets import (
    _create_read_toolset as _,
    _create_crawl_toolset as _,
    _create_browser_toolset as _,
)
from tools.undo_manager import UndoManager


_SYSTEM_PROMPT = (
    "If any high-risk import operation "
    "(such as import_csv_to_db or import_excel_to_db) is denied, "
    "stop all tool calls and file modifications immediately. "
    "Do not try alternative tools or workarounds. "
    "Only explain that you cannot proceed without permission."
)


def _build_agent(config: AppConfig, resolved_model: str, browser_enabled: bool = False) -> Agent[Settings, str | DeferredToolRequests]:
    audit_hooks = build_audit_hooks()
    undo_hooks = build_undo_hooks()
    model = build_model(config.llm_provider, resolved_model, config.workspace_id)
    exclude = None
    if not browser_enabled:
        exclude = {"browser"}
    return Agent(
        model=model,
        deps_type=Settings,
        output_type=[str, DeferredToolRequests],
        tools=get_all_tools(exclude_categories=exclude),
        capabilities=[audit_hooks, undo_hooks],
        system_prompt=_SYSTEM_PROMPT,
    )


def get_agent(
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
) -> Agent[Settings, str | DeferredToolRequests]:
    active_provider = provider or config.llm_provider
    resolved = (
        resolve_model(active_provider, model) if model else config.resolved_model
    )
    if config.db_url:
        config.undo_manager = UndoManager(config.db_url, config.workspace_id or "")
    return _build_agent(config, resolved, browser_enabled=config.browser_enabled)


def reset_agent_cache() -> None:
    return None
