# AGENTS.md

## Quick commands
```bash
uv sync                            # install deps (first time)
uv run pytest tests/               # all tests (pytest-asyncio, auto mode)
uv run pytest tests/test_tools.py  # single test file

uv run python main.py              # interactive dispatcher (no args = text menu)
uv run python main.py setup        # configure provider + API key (needs workspace)
uv run python main.py ask "query"  # single-shot query (needs workspace)
uv run python main.py serve        # FastAPI backend (0.0.0.0:8000, reload on)

npm run dev                        # backend + frontend (backend uses --no-reload)
npm run dev:api                    # FastAPI backend only (reload on)
npm run dev:web                    # Vite frontend only (proxies /api -> localhost:8000)
cd frontend && npm run build       # TypeScript + Vite production build
cd frontend && npm run test        # vitest run
cd frontend && npm run test:watch  # vitest watch
```

## Architecture
- **`config/`**: `Settings` dataclass, `secrets` (keyring-based, 8 providers), `models` (provider model listing + fuzzy matching), `canonical_models` (cross-provider model identity registry), `workspace_*` (workspace registry, paths, settings, loader)
- **`agents/db_agent.py`**: `get_agent()` builds a `pydantic_ai.Agent[Settings]` singleton with `read_toolset`, `write_toolset`, `viz_toolset` toolsets
- **`tools/`**: `db_tools` (SQLite schema/query), `data_tools` (CSV/files), `export_tools` (Excel), `viz_tools` (matplotlib), `sandbox` (Python execution)
- **`cli/`**: Typer app with `setup`, `forget`, `models`, `ask`, `interactive`, `serve` commands + `workspace` subcommands + text-based dispatcher (`cli/dispatcher.py`)
- **`server/`**: FastAPI app with session-based chat endpoint (SSE streaming), schema endpoint, sessions, settings
- **`frontend/`**: separate npm project (React 19 + Vite + TypeScript + HeroUI v3), proxies `/api` to the FastAPI backend

## Workspaces (critical)
Most CLI commands require an active workspace. Without one they exit with an error.
- `uv run python main.py workspace create /path/to/project --name my-project`
- `uv run python main.py workspace switch <id_or_name>`
- `uv run python main.py workspace list`
- `uv run python main.py workspace current`
- `serve` auto-loads the last-active workspace on startup
- Workspace registry: `~/.config/scriptordb/workspaces.json`
- Per-workspace settings: `<project>/.scriptordb/settings.json`
- Legacy global config (`~/.config/scriptordb/config.json`) is auto-migrated on first run

## Key quirks
- Package manager is `uv` (use `uv run`, `uv sync`), not pip — `requirements.txt` is a frozen snapshot
- API keys are stored in the OS keychain via `keyring`, not in `.env` files
- `nim` and `together` providers use `OpenAIChatModel` with a custom `OpenAIProvider(base_url=…)`; other providers use pydantic-ai native models
- Model names use `provider:model_name` prefix format (e.g., `openai:gpt-4o`); `resolve_model()` handles prefixing
- `Settings.db_url` defaults to `sqlite:///scriptordb.sqlite` — the tools strip the `sqlite:///` prefix when connecting
- Sessions persist per-workspace at `<project>/.scriptordb/sessions/` (24h TTL)
- The `api` directory is gitignored (`fastmcp` is in requirements, but there is no active code in-tree)
- Model list is cached per-provider at `~/.cache/scriptordb/models_<provider>.json` with 1h TTL
- No linter or formatter is configured (no `ruff.toml`, no `mypy.ini`); only `pyright` is set up for IDE use via `pyrightconfig.json`
- No CI workflows or pre-commit hooks exist in the repo
- Tests use `pydantic_ai.models.test.TestModel` — they never call a real LLM API
- Do NOT fix TypeScript / TSX type errors without explicit instruction — the user will inspect the files and provide the specific errors to address; do not modify `.ts` / `.tsx` files on your own initiative to resolve type issues
- `main.py` with no args enters the dispatcher (text menu); with any arg delegates directly to the Typer CLI
- `npm run dev` passes `--no-reload` to uvicorn to avoid reloader conflicts with concurrently; `npm run dev:api` does not
- If there are any backend changes, prompt the user to restart the backend
- Do not make unnecessary assumptions or perform extra troubleshooting steps that the user has not asked for; when asked for a cause, give the most direct one based on available information and do not investigate unrelated angles.
