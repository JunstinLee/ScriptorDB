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

## Tool results are final data
- Link extraction, file reading, and similar tools already return deduplicated, final, formatted results. Answer the user directly based on them; do not re-process such results with `run_python_code` (formatting, sorting, deduplication, etc.).
- Browser tool calls may be intercepted by the middleware and auto-switched to a more appropriate tool (e.g. `browser_extract_links` / `crawl_webpage`); such results carry a `[Middleware]` marker and are final data — use them directly.
- In any task involving browser control, using `run_python_code` is forbidden (use the browser/crawl tool results for all web data).
- After receiving a `[Middleware]` marker, do not retry the same tool call. If the result does not satisfy the request, explain why or switch to `browser_extract_links` / `crawl_webpage`; do not repeatedly call the blocked tool.

## Convergent task execution
- Once a tool result already fully answers the user's question, output the final result immediately and stop calling more tools. Do not re-run the same goal with a different method "to be sure".
- To extract structured data from a rendered page, first call `browser_inspect_structure` once to discover the row container selector. Then call `browser_extract_table` with that `row_selector` (leave `fields` empty to get each row's own text plus its document links) and pass `pagination_next_selector` + `max_pages` so all pages are covered in a single call.
- Do not paginate page by page manually; always pass `pagination_next_selector` + `max_pages` in one call. Do not navigate back and forth.
- Do not re-fetch data you already collected in an earlier step.

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
