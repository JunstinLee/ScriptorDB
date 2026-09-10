# Repository Guidelines

## Project Overview

ScriptorDB is a natural-language database agent: ask questions in plain English and the agent reads, queries, and writes your SQLite/MySQL database, imports CSV/Excel, generates matplotlib charts, runs a sandboxed Python subprocess, crawls web pages (crawl4ai), and drives a real (visible) Playwright browser — all behind human approval gates and a grouped undo system.

Three surfaces share one workspace model and one config:

- **Typer CLI** (`main.py` → `cli/`) — no-arg invocation runs a Chinese numbered text-menu dispatcher (`cli/dispatcher.py`, COMMAND_MAP 1–8); subcommands `setup`, `forget`, `models`, `ask`, `interactive`, `serve`, `workspace`, `undo`.
- **FastAPI server** (`api/`) — REST + SSE streaming; the React SPA talks to it (18 routers).
- **React SPA** (`frontend/`) — React 19 + Vite 8 + HeroUI v3 + Tailwind v4; no router, no state library.

The agent is a `pydantic_ai.Agent` built in `agents/db_agent.py` with `deps_type=Settings`; `config/settings.py` aliases `Settings = AppConfig`, so deps are the `AppConfig` dataclass. Every tool is registered by decorator into a category toolset and returns a uniform `ToolResult`.

## Architecture & Data Flow

Layering: `config/` (workspace + provider state) → `agents/` (agent builder, capabilities, agent cache) → `tools/` (category-registered tools) → `browser/` + `database/` → `runtime/` (runner pipeline, approvals, persistence) → `services/` (thin sync layer) → `schemas/` (pydantic DTOs). `cli/` and `api/` are the two entry surfaces.

**Query path:** CLI `ask`/`interactive` or `POST /api/sessions/{id}/chat` → `services/prompt_service.augment_prompt` (attachments, crawl_url) → `ApprovalOrchestrator.start_run` → `runtime/approval/resumable.run_agent_stream_resumable` → `runtime/runner/lifecycle.run_agent_stream` (queue-based event loop + `EventTranslator`; `agent.run(prompt, deps=config, event_stream_handler=…, usage_limits=UsageLimits(request_limit=200))`) → tools hit `DatabaseRepository(ctx.deps.db_url, workspace_id)` or `browser.get_manager()` → `ToolResult` events stream back as SSE frames (`api/sse_format.py`) or CLI echo. The CLI path bypasses the `AppContext` agent cache and calls `get_agent(config, …).run_sync(...)` directly.

**Approval pause semantics (load-bearing):** tools declared `requires_approval=True` surface `DeferredToolRequests`. `runtime/approval/policy.py` auto-approves `LOW_RISK_WRITE_TOOLS` (write_csv, write_file, export_excel, create_table, execute_ddl, write_data, python_sandbox_execute), gates `HIGH_RISK_IMPORT_TOOLS` (import_csv_to_db, import_excel_to_db) on `IMPORT_ROW_THRESHOLD = 100` rows, and always gates `HUMAN_APPROVAL_TOOLS` = {browser_apply_filter}, whose args are editable via `override_args`. `POST /api/sessions/{id}/approve` (`api/routes/approve.py`) calls `orchestrator.signal_approval`, which builds `ToolApproved`/`ToolDenied` and wakes the suspended run — events continue on the **original SSE stream**; a new stream is never opened and the run is never restarted. `api/routes/chat.py` keeps live runs in the module-level `_active_orchestrators` dict and gates persistence via `_should_persist` (status `completed`, or `error_type == "site_unavailable"`). `runtime/approval/policy.py` also defines an `ApprovalPolicy` dataclass that nothing consumes — policy is hardcoded constants.

**Human takeover:** after every `browser_*` tool result, `runtime/runner/takeover_hook.py` runs autofill/decision logic and `browser/takeover.py:detect_human_needed` (captcha families, CN security-verification titles, MFA/OTP inputs, OAuth URLs, anti-bot/Cloudflare, file upload, checkout, QR login, password login pages), plus `detect_timeout_trigger` / `detect_element_failure_trigger` at ≥3 occurrences. On trigger the run suspends **in place** (`resume_event.wait()`), a checkpoint is stored per session, `HumanTakeoverState` advances RUNNING → DETECTED → WAITING_HUMAN, and a 150 s countdown (`TAKEOVER_TIMEOUT = 150`) starts with a `human_takeover_request` frame. Resume via `POST /api/browser/takeover/complete` (`resume_takeover`, run_id-validated); cancel persists a cancelled run.

**Persistence:** sessions are JSON per workspace via `runtime/session_file_store.FileSessionStore` (`<ws>/.scriptordb/sessions/YYYY/MM/<session_id>.json` + `_index.json`, both `version: 2`; model-message parts round-trip UserPrompt/Text/ToolCall/ToolReturn, redacted by `runtime/redact.py`); fallback storage is `~/.config/scriptordb/global_sessions`. Legacy `~/.config/scriptordb/sessions.json` is migrated then renamed `.bak`. Note: `FileSessionStore.cleanup_expired()` is an **empty no-op** — the 24 h session TTL is not implemented. Undo groups live in the workspace DB (`_scriptordb_undo_groups` / `_scriptordb_undo_entries`, DDL in `tools/undo/repository.py`) and `UndoRepository` replays `undo_sql` in reverse `sequence` on revert.

**Workspaces (critical):** most CLI commands and API endpoints require an active workspace; without one the CLI prints a hint and exits 1 (`cli/cmd_common.ensure_workspace` → `typer.Exit(1)`), and the API returns 409 `WORKSPACE_NOT_SELECTED` (`api/dependencies.require_workspace`). Registry: `~/.config/scriptordb/workspaces.json` (`version: 1`, ids `ws_<10 hex>`); `load_default_workspace()` restores the persisted `last_active_workspace_id`. Per-workspace state: `<ws>/.scriptordb/settings.json`, `sessions/`, `outputs/`, `browser_profiles/`. New workspaces default to `sqlite:///<ws>/scriptordb.sqlite`; MySQL uses `mysql+pymysql://user@host:port/db` with the password stripped into keyring by the registry. Global defaults `~/.config/scriptordb/global_settings.json` are applied unconditionally by `apply_global_defaults` (per-workspace override is a TODO). `serve` does not require a workspace — it warns that workspace endpoints will 409.

**DB access split:** `database/session.py` is a raw pymysql + DBUtils `PooledDB` pool (MySQL only, used by `services/mysql_service.py`). `database/connection.py` + `database/repository.py` are the SQLAlchemy layer (`DatabaseRepository`, `EnginePool`, `StaticPool` for sqlite, keyring-fetched MySQL password) used by tools/services.

## Key Directories

- `config/` — `app_config.py` (`AppConfig`), `settings.py` (`Settings` alias, load/persist, deprecated `settings` singleton), `workspace_paths.py` / `workspace_registry.py` / `workspace_settings.py` / `workspace_loader.py` (registry, per-ws state, legacy migration), `secrets.py` (keyring, `SUPPORTED_PROVIDERS`), `models/` (resolver, canonical registry, client, 1 h cache).
- `agents/` — `db_agent.py` (agent builder, inline `_SYSTEM_PROMPT`), `capabilities.py` (audit + undo hooks), `app_context.py` (agent cache). `agents/prompts/` exists but is empty.
- `tools/` — `@db_tool` tools, auto-discovered. `db_tools.py` (`python_sandbox_execute` + re-exports), `db_tools_read.py`, `db_tools_write.py`, `db_tools_undo.py`, `data_tools.py`, `import_tools.py`, `export_tools.py`, `viz_tools.py`, `sandbox.py`, `validators.py`, `errors.py`, `tool_decorators.py`, `registry.py`, `toolsets.py`; subpackages `browser_tools/`, `crawl/`, `download/`, `pdf/`, `undo/`, `policy/`, `parsers/`.
- `browser/` — `manager.py` (singleton, visible Chromium, idle-close 60 s), `takeover.py` (state machine), `profiles.py` (keyring-backed, JSON index), `autofill.py`, `login_form.py`, `login_watcher.py`, `login_state.py`, `highlights.py`, `tabs.py`, `actions.py`, `sensitive.py`.
- `runtime/` — `runner/` (lifecycle, translator, events, finalize, errors, takeover_hook), `approval/` (orchestrator, policy, store, pause, persist, resumable, controller), `session_file_store.py`, `session_model.py`, `tool_middleware.py`, `run_tracker.py`, `run_control.py`, `redact.py`, `site_unavailable.py`.
- `database/` — pymysql pool (`session.py`) + SQLAlchemy (`connection.py`, `repository.py`).
- `api/` — `app.py`, `dependencies.py`, `sse_format.py`, `routes/` (18 routers incl. `chat.py`, `approve.py`, `browser_interact.py`, `browser_stream.py`, `login_credentials.py`). `api/services/` is dead (stale `__pycache__` only) — do not add code there.
- `cli/` — Typer app, one `cmd_*.py` per subcommand, `workspace_cli.py`, `dispatcher.py` (text menu), `cmd_common.py` (workspace guard).
- `services/` — thin sync business layer (`*_service.py`).
- `schemas/` — pydantic DTOs; `__init__.py` is a re-export hub, `tool.py` holds `ToolResult`/`ToolErrorInfo`, `sse.py` the SSE DTOs.
- `core/` — logging: `logging_setup.py` (logger `scriptordb.<name>`), `log_to_file.py` (import side-effect redirecting stdout/stderr to `logs/run_<ts>.log`).
- `frontend/` — React SPA: `src/api/`, `src/hooks/`, `src/components/`, `src/common/`, `src/settings/`, `src/utils/`, `src/i18n/`, `src/types/index.ts`.
- `scripts/` — three standalone diagnostic CLIs (dev tools, not tests).
- `tests/` — pytest suite in sub-packages mirroring the source layout.
- `DOCS/` — gitignored Obsidian vault for plans/design docs, plus `DOCS/PULL_REQUEST_GUIDELINES.md`.

## Development Commands

```bash
# Backend (uv; run from repo root — imports are top-level, no src package)
uv sync                                  # install deps; uv.lock is the dependency source of truth
uv run python main.py                    # no-arg → workspace selection menu + numbered text dispatcher
uv run python main.py setup              # provider + API key wizard (requires workspace)
uv run python main.py forget             # delete stored credentials (requires workspace)
uv run python main.py models             # list / fuzzy-match models (requires workspace)
uv run python main.py ask "query"        # single-shot (requires workspace)
uv run python main.py interactive        # REPL (requires workspace)
uv run python main.py serve              # FastAPI 0.0.0.0:8000; --reload defaults True
uv run python main.py workspace create <path> [--name X]   # also: switch | list | current | rename | remove | migrate
uv run python main.py undo list
uv run python main.py undo revert <group_id>

# Frontend
npm install                              # root: only installs `concurrently`
cd frontend && npm install               # UI dependencies
npm run dev                              # API (--no-reload) + Vite together
npm run dev:api                          # API only, reload on
npm run dev:web                          # Vite only; proxies /api (incl. WebSocket) -> localhost:8000
cd frontend && npm run build             # tsc -b && vite build
cd frontend && npm run lint              # ESLint 10 flat config, ts/tsx only
cd frontend && npm run test              # vitest run

# Dev diagnostics (plain scripts, not part of the test suite)
uv run python scripts/browser_stream_diag.py [--frames N] [--timeout S]
uv run python scripts/browser_viewport_diagnostic.py [--visual] [--trigger] [--timeout S]
uv run python scripts/layout_diagnostic.py <url> [-d 30] [-i 200] [-n 20] [--headed]
```

`npm run dev` passes `--no-reload` to uvicorn to avoid reloader conflicts with `concurrently`; `dev:api` leaves reload on. `/api` proxy means no CORS needed in dev.

## Code Conventions & Common Patterns

- **Tool contract:** every tool returns `schemas.tool.ToolResult{success, output, data, error: ToolErrorInfo{category, message}}` — tools never raise to the model. Arg validators raise `ModelRetry`; unexpected exceptions map through `tools/errors._to_tool_error`, with non-user-visible `ErrorCategory` values masked behind a generated `error_id` (`ContextVar` set by `agents/capabilities.py:build_audit_hooks`).
- **Tool registration:** `@db_tool(name=None, category="read", timeout=10, max_retries=1, requires_approval=False, validator=None, sequential=False)` in `tools/tool_decorators.py`. Categories in use: `read` (default), `write`, `viz`, `crawl`, `browser`, `download` (~47 tools; most are `browser`). Modules are auto-imported by pkgutil in `tools/toolsets.py` — a new file no longer needs manual registration, but subpackage tools must be re-exported from their `__init__.py`. `get_all_tools(exclude_categories=…)` drops whole categories (`{"browser"}` when browser is disabled). Approval is opt-in per tool; the 10 `requires_approval=True` tools are `python_sandbox_execute`, `write_csv`, `write_file`, `export_excel`, `create_table`, `execute_ddl`, `write_data`, `import_csv_to_db`, `import_excel_to_db`, `browser_apply_filter`.
- **Tool middleware:** `tools/tool_decorators._wrap_browser_tool` wraps `category == "browser"` tools **and** `python_sandbox_execute`; the wrapper owns `asyncio.wait_for` (framework timeout is set to `None`), routes sync callables through `asyncio.to_thread`, and calls `runtime/tool_middleware.evaluate_call`/`execute_switch` (blocks `browser_query`/`get_text`/`evaluate`/`python_sandbox_execute` in document-extraction contexts and auto-switches to `extract_links`/`crawl_webpage`, logging `[Middleware]`).
- **SQL:** raw SQLAlchemy `text()` via `DatabaseRepository` inside `repo.session()`; dialect-branch sqlite vs mysql (RETURNING vs `LAST_INSERT_ID`); identifiers quoted with `quote_identifier`; DML tools record undo entries.
- **Error handling:** tool failures are data, not exceptions. Runner-level errors live in `runtime/runner/errors.py` (`SiteUnavailableError`, `find_rate_limit` for HTTP 429 via exception-group walking, `MAX_CONNECTION_RETRIES = 2`). aiohttp `ClientError` retries ≤2.
- **Async split:** `tools/`, `browser/`, `runtime/`, `crawl/`, `download/`, `pdf/` are async; `config/`, `database/`, `services/` are sync (except `prompt_service.augment_prompt`); sync tools run through `asyncio.to_thread`; the sandbox runs sync code in a subprocess (rlimits + RSS monitor in `tools/sandbox.py`).
- **DI:** tools receive `RunContext[Settings]` (≡ `RunContext[AppConfig]`) and read `ctx.deps.db_url` / `workspace_id` / `workspace_path` / `undo_manager` / `chat_session_id` / `run_id` / `chat_prompt` / `browser_middleware_enabled`. `api/routes/chat.py` copies the config per run so concurrent sessions do not overwrite shared state. The module-level `config.settings.settings` singleton is **deprecated** but still imported by `main.py`, `api/`, most of `cli/`, and several services — pass `AppConfig` explicitly in new code. Browser is a module singleton via `browser.get_manager()`.
- **Naming:** snake_case modules; CLI = one `cmd_<name>.py` per subcommand; API routes `api/routes/<domain>.py` with `APIRouter(prefix=…, tags=…)`; services `<domain>_service.py`; test files `test_<area>.py` with `TestXxx` classes and `test_<behavior>` names (Chinese docstrings stating intent); frontend hooks `useXxx`, colocated `*.test.ts(x)`.
- **Logging:** `core.logging_setup.get_logger(__name__)` everywhere (`scriptordb.<name>`, idempotent configure, stderr filter + file handler); env vars `SCRIPTORDB_LOG_LEVEL` (default INFO), `SCRIPTORDB_LOG_DIR` (default `logs`). `core/log_to_file.py` is imported only by `api/app.py`, so `serve` redirects stdout/stderr to `logs/run_<ts>.log` while plain CLI commands do not.
- **Frontend:** no router (tabs + modals only), no state library — React context only for theme (`useTheme`), everything else custom hooks (`useReducer` for runs). All API calls go through `src/api/core.ts request<T>()` + the `src/api/client.ts` re-export hub. SSE whitelist lives in `src/api/stream.ts` (currently 15 event types) with the `StreamRunEvent` union in `src/types/index.ts` — extend **both** when adding an event. localStorage keys are `scriptordb:`-prefixed. Use the Tailwind v4 semantic tokens defined in `src/index.css` (`bg-background`, `text-foreground`, `border-grid`, `bg-surface`, `text-cobalt`/`text-accent`, `text-muted`, `text-graphite`, `text-danger`) — no raw hex in JSX. Lightweight en-only i18n via `t(key, params)` in `src/i18n/`. Debug `console.log` with bracketed tags (`[stream]`, `[useRuns]`, …) is an existing pattern — match it. Human takeover UI must never render detected login field details — `loginForm` is internal state for autofill/credential flows; do not add field lists or `ROLE_LABELS`-style display logic to `HumanTakeoverPanel`/`HumanTakeoverDrawer`, and keep `loginForm` out of the takeover drawer from `BrowserWorkspace`.
- **Working conventions:** user-reported state (errors, failures, observations) is ground truth — act on it, don't re-run checks to confirm it. Never verify framework/library behavior by reading vendored source (`site-packages`, `node_modules`) — use docs or the web. Do not fix TypeScript/TSX type errors without explicit instruction. After changing backend code, prompt the user to restart the backend. Describe verification in plain language ("run it and see the result"), not jargon. Save plans/design docs in `DOCS/` (gitignored). PR descriptions follow `DOCS/PULL_REQUEST_GUIDELINES.md`: a short `Description` of the form `[类型] + [核心变更] + [目标/原因]`, plus a structured `Extended description` (Overview / Background / Changes / Design / Testing / Impact / Notes).

## Important Files

- Entry points: `main.py`, `cli/commands.py`, `cli/dispatcher.py`, `api/app.py`.
- Agent core: `agents/db_agent.py`, `agents/capabilities.py`, `agents/app_context.py`, `runtime/runner/lifecycle.py`, `runtime/runner/translator.py`.
- Approval/takeover: `runtime/approval/orchestrator.py`, `runtime/approval/policy.py`, `runtime/approval/resumable.py`, `runtime/runner/takeover_hook.py`, `browser/takeover.py`.
- Tool machinery: `tools/tool_decorators.py`, `tools/registry.py`, `tools/toolsets.py`, `tools/errors.py`, `tools/db_tools*.py`.
- API hotspots: `api/routes/chat.py` (SSE + orchestrator lifecycle), `api/routes/approve.py`, `api/routes/browser_interact.py`, `api/routes/browser_stream.py` (WebRTC WS), `api/sse_format.py`.
- Config/secrets: `config/secrets.py`, `config/settings.py`, `config/app_config.py`, `config/workspace_registry.py`, `config/workspace_paths.py`, `config/models/resolver.py`.
- Persistence: `runtime/session_file_store.py`, `runtime/session_model.py`, `tools/undo/repository.py`, `tools/undo/manager.py`, `database/repository.py`.
- Browser: `browser/manager.py`, `browser/profiles.py`, `browser/autofill.py`, `browser/login_watcher.py`.
- Frontend: `frontend/src/main.tsx`, `src/App.tsx`, `src/components/MainApp.tsx`, `src/api/stream.ts`, `src/hooks/useChatStream.ts`, `src/hooks/useRuns.ts`, `src/types/index.ts`, `src/index.css`.
- Build/tooling: `pyproject.toml`, `uv.lock`, `pyrightconfig.json`, `frontend/package.json`, `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/eslint.config.js`.

## Runtime/Tooling Preferences

- **Python ≥3.10 via `uv`** (`requires-python = ">=3.10"`; the maintained `.venv` is CPython 3.12). No console scripts and no build backend — launch with `uv run python main.py` from the repo root. `uv.lock` is the dependency source of truth; **`requirements.txt` is a stale partial `pip freeze` snapshot (missing 11 of the 18 direct deps) — never install from it.**
- **No CI, no pre-commit, no Makefile, no Dockerfile, no `.python-version`, no `ruff`/`mypy`/`pyright` installed.** `pyrightconfig.json` (+ `[tool.pylance]`) only points IDE type-checking at `./.venv`.
- **Two independent npm projects** (no workspaces, no `engines` pin). Root `package.json` holds only `concurrently` and orchestrates the two dev processes; `frontend/package.json` holds the app stack: Vite 8, React 19, TypeScript ~6.0, Tailwind CSS 4 (`@tailwindcss/vite`, no tailwind/postcss config files — CSS-first `@theme` in `src/index.css`), HeroUI v3, ESLint 10 flat config (`ts/tsx` only, `react-hooks/set-state-in-effect` off), Vitest 4 + jsdom + Testing Library. `frontend/tsconfig*.json` does **not** enable `strict`.
- **Providers:** exactly four, all OpenAI-compatible — `openrouter` (`openrouter:` prefix) and `nim`/`together`/`deepseek` (`openai:` prefix via `OpenAIProvider(base_url=…)`); `SUPPORTED_PROVIDERS` in `config/secrets.py`, and the frontend chat popover list is duplicated in `frontend/src/constants.ts` (same 4 — keep in sync). Model selection: `resolve_model()` prefixes the provider, `fuzzy_match_model()` matches substrings; model lists cached at `~/.cache/scriptordb/models_<provider>.json` with 1 h TTL.
- **Secrets:** OS keyring only, never `.env` (no `.env` files exist). Keyring service `scriptordb:<workspace_id>`; API keys, MySQL password, and browser profiles (base64 chunks ≤1 MiB, version 2) all live there.
- **Logs:** `logs/run_<timestamp>.log` via `core/log_to_file.py`; levels/dir via `SCRIPTORDB_LOG_LEVEL` / `SCRIPTORDB_LOG_DIR`; `SCRIPTORDB_DB_URL` is used by the sandbox subprocess.

## Testing & QA

- **Backend (pytest):** `uv run pytest tests/` from the repo root. Tests live in sub-packages mirroring the source: `tests/browser/` (10 files), `tests/tools/` (9), `tests/takeover/` (8), `tests/runner/` (7), `tests/config/` (5), `tests/credential_autofill/` (3), `tests/runtime/` (2) — ~44 files, plus `tests/conftest.py`. `asyncio_mode = "auto"` (bare `async def test_*` works, no decorators) and the `slow` marker are configured in `pyproject.toml`.
  - `tests/conftest.py` provides fixtures `cleanup_browser` (reset + close per browser test) and `test_settings` (sqlite tmp DB), plus helpers `_auto_approve_handler`, `_make_ctx`, `_write_xlsx`.
  - Agent/stream tests use `pydantic_ai.models.test.TestModel`/`FunctionModel` — zero real LLM calls.
  - `@pytest.mark.slow` marks real-browser/live-network tests; **all 15 slow tests live in `tests/browser/`** and they are **NOT auto-skipped**. Fast suite: `uv run pytest tests/ -m "not slow"`; browser suite: `uv run pytest tests/ -m slow`. Browser test modules use `pytestmark = pytest.mark.usefixtures("cleanup_browser")`.
- **Frontend (Vitest):** `cd frontend && npm run test` (`test:watch` / `test:ui` also exist). jsdom environment, setup `src/test/setup.ts` (jest-dom, ResizeObserver/matchMedia stubs, localStorage + theme-attr cleanup), include glob `src/**/*.test.{ts,tsx}`. ~22 colocated test files under `src/hooks/`, `src/api/`, `src/utils/`, `src/components/`.
- **Acceptance by change type — do not run the whole suite as a blanket check:**
  - Logging statements / plain-text substitutions → import verification only (module imports cleanly), no tests.
  - Other code changes → run only the relevant tests; if none exist, an import check + LSP diagnostics pass.
  - UI changes → verify against the running app (`npm run dev`), not unit tests.
  - No coverage tooling or targets are enforced anywhere; no CI runs tests.
