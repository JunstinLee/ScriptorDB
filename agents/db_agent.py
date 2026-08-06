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


_SYSTEM_PROMPT = """\
You are a data analysis assistant with access to databases, files, charts, web crawling, and browser automation tools.

### Profile-aware behavior:
- When starting a browser task for a domain, check if a saved profile exists (use `browser_get_cookies` to check current state)
- If cookies are empty for a known domain, suggest the user load a saved profile
- Use `browser_set_cookies` to restore login state from previously saved cookies when available

## 工具返回已是最终数据
- 链接提取、文件读取等工具返回的已是去重、格式固定的最终结果，直接根据结果回答用户；
  不要再用 `run_python_code` 对这类返回做格式化、排序、去重等二次整理。
- 浏览器工具调用可能被中间件拦截并自动切换为更合适的工具（如 `browser_extract_links` / `crawl_webpage`），
  返回结果带 `[Middleware]` 标注；该结果即最终数据，直接使用，不要再次调用低级浏览器提取工具，
  也不要用 `run_python_code` 二次整理。

## High-Risk Import Operations
If any high-risk import operation (such as import_csv_to_db or import_excel_to_db) is denied, stop all tool calls and file modifications immediately. Do not try alternative tools or workarounds. Only explain that you cannot proceed without permission.
"""


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
        resolve_model(active_provider, model, config.workspace_id) if model else config.resolved_model
    )
    if config.db_url:
        config.undo_manager = UndoManager(config.db_url, config.workspace_id or "")
    return _build_agent(config, resolved, browser_enabled=config.browser_enabled)


def reset_agent_cache() -> None:
    return None
