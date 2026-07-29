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

When performing browser automation tasks, you have access to `browser_request_human_takeover(reason)` tool to pause and request human intervention. Use this tool when you encounter:

1. **Login pages**: Any page that requires username/password authentication (e.g., `/login`, `/signin`, auth walls)
2. **CAPTCHA / Verification**: Image CAPTCHA, reCAPTCHA, hCaptcha, or any visual verification challenge
3. **Multi-Factor Authentication (MFA)**: 2FA codes, SMS verification, authenticator app prompts, security key requests
4. **Permission / Consent**: OAuth authorization pages, permission grants, "Allow access" screens, cookie consent (only when required for function)
5. **HTTP 403 / 401 errors**: Access denied pages that require authentication or elevated permissions
6. **Rate limiting**: 429 Too Many Requests with manual verification requirements
7. **Payment / Checkout**: Payment confirmation pages, card verification
8. **Unexpected modals**: Popups, dialogs, or overlays that block normal interaction and cannot be dismissed programmatically
9. **Anti-bot detection**: "Are you a human?" checks, Cloudflare challenges, or similar bot-detection pages

### Guidelines for requesting takeover:
- Call `browser_request_human_takeover(reason)` with a clear, specific reason describing what you need the human to do
- Include the current page URL and what action you were trying to perform
- After the human completes the operation, you will receive a response describing what was done — continue from there
- Do NOT attempt to bypass or automate authentication mechanisms — always request human takeover instead
- If you're unsure whether a page requires human intervention, request takeover as a precaution

### Profile-aware behavior:
- When starting a browser task for a domain, check if a saved profile exists (use `browser_get_cookies` to check current state)
- If cookies are empty for a known domain, suggest the user load a saved profile
- Use `browser_set_cookies` to restore login state from previously saved cookies when available

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
        resolve_model(active_provider, model) if model else config.resolved_model
    )
    if config.db_url:
        config.undo_manager = UndoManager(config.db_url, config.workspace_id or "")
    return _build_agent(config, resolved, browser_enabled=config.browser_enabled)


def reset_agent_cache() -> None:
    return None
