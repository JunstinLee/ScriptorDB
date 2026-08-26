# AGENTS.md

## Quick commands

Backend (`uv`):
```bash
uv sync                            # install deps (first time)
uv run pytest tests/               # all tests (pytest-asyncio, auto mode)
uv run pytest tests/ -m "not slow" # fast tests only (see "Testing" below)
uv run pytest tests/test_tools.py  # single test file

uv run python main.py              # no args -> text-menu dispatcher
uv run python main.py setup        # configure provider + API key (needs workspace)
uv run python main.py ask "query"  # single-shot query (needs workspace)
uv run python main.py interactive  # REPL mode (needs workspace)
uv run python main.py serve        # FastAPI backend: 0.0.0.0:8000, --reload default

uv run python main.py undo list
uv run python main.py undo revert <group_id>
```

Frontend (`npm`):
```bash
npm install                 # root only installs `concurrently`
cd frontend && npm install  # UI dependencies

npm run dev                        # backend + frontend (backend uses --no-reload)
npm run dev:api                    # backend only (reload on)
npm run dev:web                    # Vite frontend only; proxies /api -> localhost:8000
cd frontend && npm run build       # tsc -b && vite build
cd frontend && npm run lint        # ESLint
cd frontend && npm run test        # vitest run
cd frontend && npm run test:watch  # vitest watch
```

## Architecture
- Run everything from repo root. Imports are top-level (`from config...`, `from cli...`); there is no `src` package.
- `config/`: `AppConfig` runtime settings, `secrets` (keyring + `SUPPORTED_PROVIDERS`), `models` (provider model listing/resolution), `canonical_models`, workspace registry/settings/loader.
- `agents/db_agent.py`: `get_agent()` builds a `pydantic_ai.Agent[Settings]` with `read_toolset`, `write_toolset`, `viz_toolset` and auto-approved deferred tool calls.
- `tools/`: SQLite schema/query (`db_tools.py`, `db_repository.py`), CSV/files, Excel export, matplotlib viz, Python sandbox, undo log/manager/repository, browser + crawl tools, validators.
- `browser/`: Playwright browser automation — lifecycle manager, context, profiles, highlights, human-takeover checkpoint mechanism.
- `cli/`: Typer app (`cli/__init__.py`), one handler per subcommand (`cmd_ask.py`, `cmd_serve.py`, ...), workspace subcommands (`cli/workspace_cli.py`), text dispatcher (`cli/dispatcher.py`).
- `api/`: FastAPI app (`api/app.py`) + routers in `api/routes/` (health, workspaces, sessions, chat SSE, approve, schema, models, settings, api_keys, files, undo, history, browser_*) + HTTP/SSE transport helpers (`dependencies.py`, `sse_format.py`, `streaming.py`).
- `runtime/`: agent runtime & core state — run pipeline (`runtime/runner/`), approval orchestration (`approval_orchestrator.py`, `approval_policy.py`, `filter_confirm.py`), session persistence (`session_model.py`, `session_file_store.py`, `sessions.py`), `run_tracker.py`, `import_inspector.py`, tool middleware (`tool_middleware.py`), output validation (`run_control.py`).
- `services/`: business service layer (chat, undo, schema, mysql, history, prompt, workspace, settings, model, api_key, setup), pydantic DTOs in `schemas/`.
- `database/session.py`: pooled MySQL connections (SQLAlchemy + PyMySQL + DBUtils pool).
- `frontend/`: separate npm project — React 19 + Vite + TypeScript + HeroUI v3 + Tailwind CSS v4.

## Workspaces (critical)
Most CLI commands and server endpoints require an active workspace. Without one, CLI exits and server endpoints return HTTP 409.
- `uv run python main.py workspace create /path/to/project --name my-project`
- `uv run python main.py workspace switch <id_or_name>`
- `uv run python main.py workspace list`
- `uv run python main.py workspace current`
- `serve` and the no-arg dispatcher auto-load the last-active workspace on startup.
- Registry: `~/.config/scriptordb/workspaces.json`
- Per-workspace state: `<project>/.scriptordb/settings.json`, `sessions/`, `outputs/`
- New workspaces default to `sqlite:///<project>/scriptordb.sqlite`.
- Global defaults: `~/.config/scriptordb/global_settings.json`. Currently every workspace uses global defaults (`use_global_defaults=True`).
- Legacy `~/.config/scriptordb/config.json` is auto-migrated on first run.

## Testing
- Tests use `pydantic_ai.models.test.TestModel` — zero real LLM calls. No conftest; `asyncio_mode = "auto"`.
- Tests marked `@pytest.mark.slow` (in `tests/test_browser*.py`) launch a real Playwright browser / hit the network and are NOT auto-skipped — `uv run pytest tests/` runs them. Use `-m "not slow"` for the fast suite.
- Whether to run tests, and which ones, is governed by the "Acceptance criteria" section below — do not run the whole suite as a blanket acceptance check.

## Acceptance criteria
Acceptance is graded by change type — never run the full test suite as a blanket check:
- **Logging statements and plain-text substitutions**: import verification only — confirm the modified module imports cleanly; do not run any tests.
- **Other code changes**:
  - Relevant tests exist: run only those tests (the relevant test file or cases), nothing unrelated.
  - No relevant tests: run an import check plus an LSP diagnostics pass (via the lsp tool) to confirm the change is error-free.

## Documentation
- Save project documentation, plans, and notes in `DOCS/` at the repo root.
- `DOCS/` is gitignored, so it is meant for local workspace docs rather than committed source files.
- Find existing docs with `ls DOCS/` or `glob("DOCS/**/*")`. `DOCS/PULL_REQUEST_GUIDELINES.md` defines the PR Description/Extended-description conventions.

## Key quirks
- Package manager is `uv` (`uv run`, `uv sync`), not pip. `uv.lock` is the source of truth; `requirements.txt` is a frozen snapshot.
- API keys live in the OS keychain via `keyring` (service `scriptordb:<workspace_id>`), never in `.env` or repo files.
- Supported providers (in `config/secrets.py`): `openai`, `anthropic`, `google`, `groq`, `mistral`, `openrouter`, `nim`, `together`, `deepseek`.
- `nim`, `together`, `openrouter`, `deepseek` use `OpenAIChatModel` with a custom `OpenAIProvider(base_url=…)` and resolve to `openai:<model>`; other providers use pydantic-ai native models with `provider:model` prefixes.
- `resolve_model()` adds the provider prefix; `fuzzy_match_model()` lets you pass a substring.
- Model lists are cached per-provider at `~/.cache/scriptordb/models_<provider>.json` with a 1h TTL.
- Sessions persist per-workspace at `<project>/.scriptordb/sessions/` (24h TTL).
- Server stdout/stderr is redirected to `logs/run_<timestamp>.log` via `log_to_file.py`; `logging_setup.py` writes `logs/` too. `SCRIPTORDB_LOG_LEVEL` and `SCRIPTORDB_LOG_DIR` env vars control it.
- Python has no configured linter or formatter; only `pyrightconfig.json` for IDE type-checking. Frontend has ESLint (`npm run lint`) and `tsc -b` type-checking during `npm run build`.
- No CI workflows or pre-commit hooks exist in the repo. Commit messages follow conventional-commits style (e.g. `feat(browser): ...`, `refactor(config): ...`) — match that style when committing.
- The `/api` directory is gitignored; `fastmcp` is in `requirements.txt` but unused in-tree.
- `npm run dev` passes `--no-reload` to uvicorn to avoid reloader conflicts with `concurrently`; `npm run dev:api` does not.
- The Vite dev server proxies `/api` to `http://localhost:8000`; backend CORS allows all origins.

## Operating conventions
- When communicating with the user, avoid jargon and hardware-sounding terms (e.g. "smoke test") as well as obscure technical slang; describe verification, checks, and run outcomes in plain language (e.g. "run it and see the result", "actually execute it in the browser").
- NEVER verify framework/library behavior by reading third-party source code in `site-packages`, `node_modules`, or similar vendored locations. To confirm a library mechanism (e.g. pydantic-ai event/cancel semantics), consult official documentation or search the web instead.
- Do NOT fix TypeScript / TSX type errors without explicit instruction — the user will inspect the files and provide the specific errors to address; do not modify `.ts` / `.tsx` files on your own initiative to resolve type issues.
- If you change backend code, prompt the user to restart the backend.
- NEVER treat "clearing every adjacent question" as the stopping condition: deliver the conclusion as soon as the question is reliably answered; run only the verification needed to answer it — no gratuitous confirmations, no off-topic follow-ups.
