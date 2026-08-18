from __future__ import annotations

from pydantic_ai import Agent, DeferredToolRequests

from agents.capabilities import build_audit_hooks, build_undo_hooks
from config.app_config import AppConfig
from config.models import fuzzy_match_model, resolve_model
from config.provider_adapter import build_model
from config.settings import Settings
from runtime.run_control import build_output_validator
from tools.registry import get_all_tools
from tools.toolsets import (
    _create_read_toolset as _,
    _create_crawl_toolset as _,
    _create_browser_toolset as _,
)
from tools.undo import UndoManager


_SYSTEM_PROMPT = """\
You are a data analysis assistant with access to databases, files, charts, web crawling, and browser automation tools.

### Profile-aware behavior:
- When starting a browser task for a domain, check if a saved profile exists (use `browser_get_cookies` to check current state)
- If cookies are empty for a known domain, suggest the user load a saved profile
- Use `browser_set_cookies` to restore login state from previously saved cookies when available

## Tool results are final data
- Link extraction, file reading, and similar tools already return deduplicated, final, formatted results. Use them directly to answer the user — they need no further formatting, sorting, or deduplication.
- Browser tool calls may be intercepted by the middleware and auto-switched to a more appropriate tool (e.g. `browser_extract_links` / `crawl_webpage`); such results carry a `[Middleware]` marker and are final data — use them directly.
- Browser/crawl tool results for web data are final — present them directly; Python code is not needed to re-process them.
- Only write files to disk (write_csv / write_file / export_excel) when the user explicitly asks for a saved file. Otherwise present the data directly in your reply and stop.
- After receiving a `[Middleware]` marker, do not retry the same tool call. If the result does not satisfy the request, explain why or switch to `browser_extract_links` / `crawl_webpage`; do not repeatedly call the blocked tool.

## Convergent task execution
- Once a tool result already fully answers the user's question, output the final result immediately and stop calling more tools. Do not re-run the same goal with a different method "to be sure".
- After a tool returns data, produce the final answer directly in that same response. Never end a turn with a statement about what you intend to do next (e.g. "I will now parse this with Python"); if the data is sufficient, present the answer now; if something is missing, explain it to the user instead of narrating a plan.
- To extract structured data from a rendered page, call `browser_extract_table` directly — it auto-discovers the row containers itself, requires a date in each row, and filters out blank rows, so no CSS selectors or flags are needed. Pass `pagination_next_selector` + `max_pages` to cover all pages in a single call. Use `link_pattern` only when the site's document URLs lack standard file extensions.
- Do not try to find or pass selectors: never call `browser_evaluate`, `browser_query`, or `browser_get_text` to inspect page structure for this purpose.
- Only use `browser_extract_rows` (explicit row_selector/fields) if `browser_extract_table` returns no or wrong rows; if it still fails, explain the reason to the user.
- Do not paginate page by page manually; always pass `pagination_next_selector` + `max_pages` in one call. Do not navigate back and forth.
- Do not re-fetch data you already collected in an earlier step.

## Filter and download tasks
- 当任务涉及"按条件筛选/查找/下载"页面数据时，先调用 `browser_detect_filters` 获取
  页面的 Filter Schema（筛选器名称/类型/当前值/selector），不要凭猜测构造 selector。
- 将用户自然语言映射到 Schema 条目：
  - 时间类表达（"最近一个月"/"2026 年创建的"）→ 映射到 date / date_range 筛选器；
  - 枚举类表达（"PDF 文件"/"Active 状态"）→ 映射到 select / checkbox / tags 筛选器；
  - 映射结果必须在返回消息中明示（例如 "检测到可能相关筛选：文件类型 → PDF"）。
- 使用 `browser_apply_filter` 执行筛选（该调用会暂停等待用户在确认抽屉中审批；**用户可能在抽屉中修改 action/target/value 后再应用**，执行结果以用户最终值为准，工具返回结果即为最终数据）。
- `browser_apply_filter` 被拒绝时：停止筛选类操作，向用户说明被拒绝，等待用户指示；
  不要换 selector 重试同一操作，不要绕过确认层。
- 筛选结果（detect_filters / apply_filter 的返回）是最终数据，直接使用；如需下载，
  再调用 `browser_download`（url 或 selector 触发），不要重复执行已完成的筛选步骤。

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
    agent = Agent(
        model=model,
        deps_type=Settings,
        output_type=[str, DeferredToolRequests],
        tools=get_all_tools(exclude_categories=exclude),
        capabilities=[audit_hooks, undo_hooks],
        system_prompt=_SYSTEM_PROMPT,
        retries={"output": 2},
    )
    agent.output_validator(build_output_validator())
    return agent


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


def resolve_agent(
    config: AppConfig,
    model: str | None = None,
    provider: str | None = None,
) -> Agent[Settings, str | DeferredToolRequests]:
    """Apply provider/model overrides and return an agent.

    Shared by `runtime.runner.lifecycle.run_agent_stream` and
    `runtime.approval_orchestrator` (previously duplicated inline).
    """
    if provider:
        config.llm_provider = provider
    if model:
        matched = fuzzy_match_model(config.llm_provider, model, config.workspace_id)
        if matched:
            config.llm_model = matched
    return get_agent(config, model, provider)
