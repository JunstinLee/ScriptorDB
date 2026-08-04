# AGENTS.md

## Quick commands

Backend (`uv`):
```bash
uv sync                            # install deps (first time)
uv run pytest tests/               # all tests (pytest-asyncio, auto mode)
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
- `config/`: `AppConfig` runtime settings, `secrets` (keyring), `models` (provider model listing/resolution), `canonical_models`, workspace registry/settings/loader.
- `agents/db_agent.py`: `get_agent()` builds a `pydantic_ai.Agent[Settings]` with `read_toolset`, `write_toolset`, `viz_toolset` and auto-approved deferred tool calls.
- `tools/`: SQLite schema/query, CSV/files, Excel export, matplotlib viz, Python sandbox, undo log.
- `cli/`: Typer app (`cli/__init__.py`), command handlers (`cli/commands.py`), workspace subcommands (`cli/workspace_cli.py`), text dispatcher (`cli/dispatcher.py`).
- `server/`: FastAPI app (`server/app.py`) mounting routers from `server/routes/` for health, workspaces, sessions, chat (SSE), schema, models, settings, api_keys, files, undo.
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

## Documentation
- Save project documentation, plans, and notes in `DOCS/` at the repo root.
- `DOCS/` is gitignored, so it is meant for local workspace docs rather than committed source files.
- Find existing docs with `ls DOCS/` or `glob("DOCS/**/*")`.

## Key quirks
- Package manager is `uv` (`uv run`, `uv sync`), not pip. `uv.lock` is the source of truth; `requirements.txt` is a frozen snapshot.
- API keys live in the OS keychain via `keyring` (service `scriptordb:<workspace_id>`), never in `.env` or repo files.
- Supported providers: `openai`, `anthropic`, `google`, `groq`, `mistral`, `openrouter`, `nim`, `together`.
- `nim` and `together` use `OpenAIChatModel` with a custom `OpenAIProvider(base_url=…)` and resolve to `openai:<model>`; other providers use pydantic-ai native models with `provider:model` prefixes.
- `resolve_model()` adds the provider prefix; `fuzzy_match_model()` lets you pass a substring.
- Model lists are cached per-provider at `~/.cache/scriptordb/models_<provider>.json` with a 1h TTL.
- Sessions persist per-workspace at `<project>/.scriptordb/sessions/` (24h TTL).
- Tests use `pydantic_ai.models.test.TestModel` — zero real LLM calls.
- Python has no configured linter or formatter; only `pyrightconfig.json` for IDE type-checking. Frontend has ESLint (`npm run lint`) and `tsc -b` type-checking during `npm run build`.
- No CI workflows or pre-commit hooks exist in the repo.
- The `/api` directory is gitignored; `fastmcp` is in `requirements.txt` but unused in-tree.
- `npm run dev` passes `--no-reload` to uvicorn to avoid reloader conflicts with `concurrently`; `npm run dev:api` does not.
- The Vite dev server proxies `/api` to `http://localhost:8000`; backend CORS allows all origins.

## Operating conventions
- Do NOT fix TypeScript / TSX type errors without explicit instruction — the user will inspect the files and provide the specific errors to address; do not modify `.ts` / `.tsx` files on your own initiative to resolve type issues.
- If you change backend code, prompt the user to restart the backend.
- Do not perform extra troubleshooting steps the user did not ask for; when asked for a cause, give the most direct one based on available information and do not investigate unrelated angles.
