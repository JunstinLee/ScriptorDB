# Repository Guidelines

## Project Overview

ScriptorDB is a natural-language database agent: ask questions in plain English and the agent reads, queries, and writes your SQLite/MySQL database, imports CSV/Excel, generates matplotlib charts, runs a sandboxed Python subprocess, crawls web pages (crawl4ai), and drives a real (visible) Playwright browser — all behind human approval gates and a grouped undo system.

Three surfaces share one workspace model and config:

- **Typer CLI** (`main.py`) — no-arg runs a Chinese numbered text-menu dispatcher; subcommands `setup`, `ask`, `interactive`, `serve`, `workspace`, `undo`.
- **FastAPI server** (`api/`) — REST + SSE streaming; the React SPA talks to it.
- **React SPA** (`frontend/`) — React 19 + Vite + HeroUI v3 + Tailwind v4, no router, no state library.

The agent itself is a `pydantic_ai.Agent[AppConfig]` built in `agents/db_agent.py`; every tool is registered by decorator into a category toolset and returns a uniform `ToolResult`.

## Architecture & Data Flow

Layered: `config/` (workspace + provider state) → `agents/` (agent builder, capabilities) → `tools/` (category-registered tools) → `browser/` + `database/` → `runtime/` (runner pipeline, approvals, persistence) → `services/` (thin sync layer) → `schemas/` (pydantic DTOs). `cli/` and `api/` are the two entry surfaces.

**Query path:** CLI `ask` or `POST /api/sessions/{id}/chat` → `services/prompt_service.augment_prompt` (attachments/crawl_url) → `ApprovalOrchestrator.start_run` → `run_agent_stream_resumable` → `runtime/runner/lifecycle.run_agent_stream` (queue-based event loop + `EventTranslator`) → `agent.run(deps=AppConfig, event_stream_handler=…)` → tools hit `DatabaseRepository(ctx.deps.db_url, workspace_id)` or `browser.get_manager()` → `ToolResult` dict events stream back as SSE frames (`api/sse_format.py`) or CLI echo.

**Approval pause semantics (load-bearing):** tools with `requires_approval=True` surface `DeferredToolRequests`. `runtime/approval/policy.py` auto-approves low-risk writes (`LOW_RISK_WRITE_TOOLS`: write_csv, write_file, export_excel, create_table, execute_ddl, write_data, python_sandbox_execute), requires human approval for imports >100 rows (`HIGH_RISK_IMPORT_TOOLS`) and always for `browser_apply_filter` (args editable via `override_args`). When approved or denied, `POST /api/sessions/{id}/approve` (`signal_approval`) wakes the suspended run — events continue on the **original SSE stream**; a new stream is never opened. `api/routes/chat.py` keeps live runs in the module-level `_active_orchestrators` dict.

**Human takeover:** after every `browser_*` tool result, `runtime/runner/takeover_hook.py` calls `detect_takeover()` (captcha/MFA/OAuth/antibot heuristics, ≥3 nav timeouts, ≥3 element failures). If triggered, the run suspends **in place** (`resume_event.wait()`), a checkpoint is stored per session, a 150s countdown starts, and `human_takeover_request` is emitted. Resume via `POST /api/browser/takeover/complete` (`resume_takeover`, run_id-validated); cancel persists a cancelled run.

**Persistence:** sessions are JSON per workspace via `FileSessionStore` (`<ws>/.scriptordb/sessions/YYYY/MM/<session_id>.json` + `_index.json`; model-message parts round-trip ToolCall/ToolReturn). Undo groups live in the workspace DB (`_scriptordb_undo_groups` / `_scriptordb_undo_entries`) and replay `undo_sql` in reverse sequence on revert. Note: `FileSessionStore.cleanup_expired()` is an **empty method** — the 24h session TTL is not implemented.

**DB access split:** `database/session.py` is a raw pymysql + DBUtils `PooledDB` pool (MySQL only, used by `mysql_service`). `database/connection.py` + `database/repository.py` are the SQLAlchemy layer (`DatabaseRepository`, `EnginePool`, `StaticPool` for sqlite, keyring-fetched MySQL password) used by tools/services.

## Workspaces (critical)

Most CLI commands and server endpoints require an active workspace; without one the CLI exits (exit 1) and the API returns 409 `WORKSPACE_NOT_SELECTED`.

- Commands: `uv run python main.py workspace create <path> [--name X]`, `switch <id_or_name>`, `list`, `current`, `rename`, `remove [--delete-files]`, `migrate`.
- Registry: `~/.config/scriptordb/workspaces.json`. Per-workspace state: `<ws>/.scriptordb/settings.json`, `sessions/`, `outputs/`, `browser_profiles/`.
- New workspaces default to `sqlite:///<ws>/scriptordb.sqlite`; MySQL uses `mysql+pymysql://user@host:port/db` with the password in keyring (never persisted to disk; `mysql_password_set` derives from keyring).
- Global defaults: `~/.config/scriptordb/global_settings.json` — `apply_global_defaults` overwrites workspace settings unconditionally (per-workspace override is a TODO).
- Legacy `~/.config/scriptordb/config.json` + sessions are auto-migrated on first run (`config/workspace_loader.migrate_legacy`).
- API keys live in the OS keychain (keyring service `scriptordb:<workspace_id>`, legacy `ScriptorDB`), never in `.env`/repo files. Browser profiles are also stored in keyring (base64-chunked, ≤1 MiB, versioned).

## Key Directories

- `config/` — `AppConfig` dataclass (runtime view of active workspace: db_url, llm_provider/model, mysql params, undo_manager, workspace_id/name/path), `secrets.py` (keyring + `SUPPORTED_PROVIDERS`), `models/` (resolver, canonical registry, client, 1h cache), workspace registry/settings/loader/global_settings, `provider_adapter.py`.
- `agents/` — `db_agent.py` (pydantic-ai Agent builder: `output_type=[str, DeferredToolRequests]`, tools from registry, audit+undo capabilities, output validator), `capabilities.py`, `app_context.py` (agent cache keyed by provider/model/workspace signature).
- `tools/` — all agent tools, registered via `@db_tool` into categories `read|write|viz|crawl|browser|download`. `db_tools.py` (query_database, get_schema, python_sandbox_execute, create_table, execute_ddl, write_data), `data_tools.py`, `export_tools.py`/`import_tools.py`, `viz_tools.py`, `sandbox.py` (subprocess + import whitelist + rlimits), `validators.py` (ModelRetry arg validators), `errors.py` (ErrorCategory → ToolResult mapping), `policy/` (pure link/crawl/download policies), `crawl/`, `download/`, `pdf/`, `browser_tools/` (navigation, dom, links, table, tabs, cookies, visual, filter_detect/filter_apply), `undo/` (UndoManager + UndoRepository).
- `browser/` — Playwright lifecycle: `manager.py` (singleton, always visible, idle-close 60s, auth-challenge tracking, takeover triggers), `takeover.py` (HumanTakeoverManager state machine), `context.py`, `profiles.py` (keyring-backed), `login_state.py`, `highlights.py`, `tabs.py`, `trace.py` (ClickTracer).
- `runtime/` — `runner/` (lifecycle, translator, events, finalize, errors, takeover_hook), `approval/` (orchestrator, policy, resumable, store, pause), `session_model.py`/`session_file_store.py`/`sessions.py`, `run_tracker.py`, `import_inspector.py`, `tool_middleware.py` (browser-tool auto-switch + filter-probe blocking), `run_control.py` (output validator).
- `api/` — `app.py` (FastAPI, CORS `*` + credentials, 18 routers, lifespan reloads workspace + session store), `routes/` (health, workspaces, sessions, chat SSE, approve, schema, models, settings, api_keys, files, undo, history, browser_state, browser_interact, browser_cookies, browser_profiles, browser_stream), `dependencies.py`, `sse_format.py`, `streaming.py`.
- `cli/` — Typer app, one handler per subcommand (`cmd_ask.py`, `cmd_serve.py`, …), `workspace_cli.py`, `dispatcher.py` (text menu, COMMAND_MAP supports numbered and named input).
- `services/` — thin sync business layer (chat, undo, schema, mysql, history, prompt, workspace, settings, model, api_key, setup).
- `schemas/` — pydantic DTOs incl. `tool.py` (`ToolResult`/`ToolErrorInfo` contract) and `sse.py` (SSE event DTOs).
- `database/` — pymysql pool (`session.py`) + SQLAlchemy (`connection.py`, `repository.py`).
- `core/` — logging: `logging_setup.py` (logger `scriptordb`), `log_to_file.py` (import side-effect redirecting stdout/stderr to `logs/run_<timestamp>.log`).
- `frontend/` — React SPA: `src/api/` (fetch wrapper + domain modules), `src/hooks/`, `src/components/`, `src/types/index.ts`, `src/i18n/`.
- `scripts/` — Python diagnostics (WebRTC browser stream, viewport, layout) — dev tools, run via `uv run python scripts/…`.
- `DOCS/` — gitignored Obsidian vault of plans/design docs (see Working Conventions).

## Development Commands

```bash
# Backend (uv; run from repo root — imports are top-level, no src package)
uv sync                                  # install deps
uv run python main.py                    # text-menu dispatcher (auto-loads last workspace)
uv run python main.py setup              # provider + API key wizard (needs workspace)
uv run python main.py ask "query"        # single-shot
uv run python main.py interactive        # REPL
uv run python main.py serve              # FastAPI 0.0.0.0:8000; --reload defaults True
uv run python main.py undo list          # grouped undo
uv run python main.py undo revert <group_id>

# Frontend
npm install                              # root: only installs `concurrently`
cd frontend && npm install               # UI dependencies
npm run dev                              # API (--no-reload) + Vite together
npm run dev:api                          # API only, reload on
npm run dev:web                          # Vite only; proxies /api -> localhost:8000
cd frontend && npm run build             # tsc -b && vite build
cd frontend && npm run lint              # ESLint (flat config, ts/tsx only)
cd frontend && npm run test              # vitest run
```

`npm run dev` passes `--no-reload` to uvicorn to avoid reloader conflicts with `concurrently`; `dev:api` leaves reload on. Vite proxies `/api` (incl. WebSocket) to `localhost:8000`, so no CORS needed in dev.

## Code Conventions & Common Patterns

- **Tool contract:** every tool returns `schemas.tool.ToolResult{success, output, data, error: ToolErrorInfo{category, message}}` — tools never raise to the model. Arg validators raise `ModelRetry`; unexpected exceptions map through `tools/errors._to_tool_error`, with internal-only error categories masked behind an `error_id`.
- **Tool registration:** `@db_tool(name, category, requires_approval, timeout, max_retries, validator, sequential)` in `tools/tool_decorators.py`; modules auto-discovered via pkgutil; `exclude_categories={"browser"}` when browser disabled. Approval is opt-in per tool: `requires_approval=True`.
- **SQL:** raw SQLAlchemy `text()` SQL via `DatabaseRepository` with `repo.session()` context manager; dialect branching sqlite vs mysql (RETURNING vs LAST_INSERT_ID); identifiers quoted via `quote_identifier`; DML tools record undo entries.
- **Error handling:** tool failures are data (`ToolResult(success=False, …)`), not exceptions; connection retries ≤2 for aiohttp ClientError; rate-limit (429) detection walks exception groups in `runtime/runner/errors.py`.
- **Async split:** tools/, browser/, runtime/, crawl/download/pdf are async; config/ and services/ are sync (except `prompt_service.augment_prompt`); the sandbox runs sync code in a subprocess. Sync tools run via `asyncio.to_thread`.
- **DI:** tools receive `RunContext[AppConfig]` and read `ctx.deps.db_url`/`workspace_id`/`undo_manager`; agents cached in `AppContext` by signature; browser is a module singleton (`browser.get_manager()`); the `config.settings` module singleton is **deprecated** — pass `AppConfig` explicitly.
- **Logging:** `core.logging_setup.get_logger(__name__)` everywhere; `core/log_to_file.py` import side-effect redirects stdout/stderr to `logs/run_<ts>.log`; env vars `SCRIPTORDB_LOG_LEVEL` (default INFO), `SCRIPTORDB_LOG_DIR` (default `logs`).
- **Naming:** `test_<area>.py` + `TestXxx` classes + `test_<behavior>` names (Chinese docstrings stating intent); frontend hooks `useXxx`, colocated `*.test.ts(x)` files.
- **Frontend:** no router (tabs + modals only), no state library — React context only for theme (`useTheme`), everything else is custom hooks (`useReducer` for runs). All API calls via `src/api/core.ts request<T>()` + `src/api/client.ts` re-export hub. SSE: 13-event whitelist in `src/api/stream.ts` + `StreamRunEvent` union in `src/types/index.ts` — extend both when adding events. localStorage keys are `scriptordb:`-prefixed. Tailwind v4 semantic tokens (`bg-background`, `text-foreground`, `border-grid`, `text-cobalt`…) defined in `src/index.css` — no raw hex in JSX. Lightweight en-only i18n via `t(key, params)` in `src/i18n/`. Debug `console.log` with bracketed tags (`[stream]`, `[useRuns]`, …) is an existing pattern — match it.

## Important Files

- Entry points: `main.py`, `cli/commands.py`, `cli/dispatcher.py`, `api/app.py`.
- Agent core: `agents/db_agent.py`, `agents/capabilities.py`, `runtime/runner/lifecycle.py`, `runtime/runner/translator.py`.
- Approval/takeover: `runtime/approval/orchestrator.py`, `runtime/approval/policy.py`, `runtime/approval/resumable.py`, `runtime/runner/takeover_hook.py`, `browser/takeover.py`.
- Tool machinery: `tools/tool_decorators.py`, `tools/registry.py`, `tools/toolsets.py`, `tools/errors.py`, `tools/db_tools.py`.
- API hotspots: `api/routes/chat.py` (SSE + orchestrator lifecycle), `api/routes/approve.py`, `api/routes/browser_interact.py`, `api/routes/browser_stream.py` (WebRTC WS), `api/sse_format.py`.
- Config/secrets: `config/secrets.py` (keyring, providers), `config/settings.py`, `config/app_config.py`, `config/workspace_registry.py`, `config/models/resolver.py`.
- Persistence: `runtime/session_file_store.py`, `runtime/session_model.py`, `tools/undo/repository.py`, `database/repository.py`.
- Browser: `browser/manager.py`, `browser/profiles.py`.
- Frontend: `frontend/src/main.tsx`, `src/App.tsx`, `src/components/MainApp.tsx`, `src/api/stream.ts`, `src/hooks/useChatStream.ts`, `src/hooks/useRuns.ts`, `src/types/index.ts`, `src/index.css`.
- Build/tooling: `pyproject.toml`, `uv.lock`, `pyrightconfig.json`, `frontend/package.json`, `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/eslint.config.js`.

## Runtime/Tooling Preferences

- **Python ≥3.10 via `uv`.** No console scripts — launch with `uv run python main.py`. `uv.lock` is the dependency source of truth; **`requirements.txt` is a stale partial snapshot (missing 12 of 18 direct deps) — never install from it.** No configured Python linter/formatter; `pyrightconfig.json` + `[tool.pylance]` point at `./.venv` for IDE type-checking.
- **Two independent npm projects** (no workspaces). Root `package.json` only holds `concurrently`. Node version is unpinned (no engines/.nvmrc). Frontend: Vite 8, React 19, TypeScript ~6 (**strict NOT enabled**), ESLint 10 flat config, Vitest 4 (jsdom, setup `src/test/setup.ts`), Tailwind v4 via `@tailwindcss/vite` (no tailwind/postcss config files), HeroUI v3.
- **Providers:** exactly four, all OpenAI-compatible — `openrouter` (`openrouter:` prefix) and `nim`/`together`/`deepseek` (`openai:` prefix via `OpenAIProvider(base_url=…)`); `SUPPORTED_PROVIDERS` in `config/secrets.py`. Model selection: `resolve_model()` prefixes provider; `fuzzy_match_model()` matches substrings. Model lists cached `~/.cache/scriptordb/models_<provider>.json`, 1h TTL. Frontend chat popover provider list is hardcoded in `frontend/src/constants.ts` (same 4).
- **Secrets:** OS keyring, never `.env`. Keyring service `scriptordb:<workspace_id>`.
- **Logs:** `logs/run_<timestamp>.log` via `core/log_to_file.py`; `SCRIPTORDB_LOG_LEVEL`/`SCRIPTORDB_LOG_DIR` env vars. No `.env` files exist.
- **No CI, no pre-commit, no Makefile.**

## Testing & QA

- **Backend (pytest):** `uv run pytest tests/` (from root; `tests/__init__.py` exists, helpers import as `from tests.conftest import …`). `asyncio_mode = "auto"` — bare `async def test_*` works without decorators. Agent/stream tests use `pydantic_ai.models.test.TestModel` (zero real LLM calls).
  - `tests/conftest.py` provides fixtures `cleanup_browser` (reset + close per browser test), `test_settings` (sqlite tmp DB), and helpers `_auto_approve_handler`, `_make_ctx`, `_write_xlsx`.
  - `@pytest.mark.slow` marks real-browser/live-network tests (`test_browser*.py`; browser test files set `pytestmark = pytest.mark.usefixtures("cleanup_browser")`). They are **NOT auto-skipped** — `uv run pytest tests/` runs them. Fast suite: `uv run pytest tests/ -m "not slow"`; browser suite: `-m slow`.
- **Frontend (Vitest):** `cd frontend && npm run test` (or `test:watch`/`test:ui`). jsdom environment, colocated `*.test.ts(x)` next to source in `api/`, `hooks/`, `components/`, `utils/`; setup in `src/test/setup.ts`.
- **Acceptance by change type (do not run the whole suite as a blanket check):**
  - Logging statements / plain-text substitutions → import verification only (module imports cleanly), no tests.
  - Other code changes → run only the relevant tests; if none exist, an import check + LSP diagnostics pass.
  - No coverage targets are enforced anywhere.

## Working Conventions

- User-reported state (errors, failures, observations) is ground truth — act on it; don't re-run checks to confirm what the user reported.
- Never verify framework/library behavior by reading vendored source (`site-packages`, `node_modules`) — consult official docs or search the web.
- Do NOT fix TypeScript/TSX type errors without explicit instruction; do not modify `.ts`/`.tsx` files on your own initiative to resolve type issues.
- After changing backend code, prompt the user to restart the backend.
- Save plans/design docs in `DOCS/` (gitignored). PR descriptions follow `DOCS/PULL_REQUEST_GUIDELINES.md`: short `Description` in the form `[类型] + [核心变更] + [目标/原因]`, plus a structured `Extended description` (Overview / Background / Changes / Design / Testing / Impact / Notes).
- Describe verification in plain language ("run it and see the result"), not jargon.
- NEVER split a single tool call into fragments: one call carries its complete, well-formed argument payload at once. For XML-bodied tools (e.g. `edit`), paired tags such as `<SM:FIND>`/`<SM:PUT>` MUST both appear inside the same `input` argument in the same call — never send one half without the other, and never route part of a call through an extra argument.
