# AGENTS.md

## Quick commands
```bash
uv run pytest tests/              # all tests (pytest + pytest-asyncio, auto mode)
uv run python main.py             # interactive dispatcher (no args = dispatcher)
uv run python main.py setup       # configure provider + API key
uv run python main.py ask "query" # single-shot query
uv run python main.py serve       # start FastAPI backend (0.0.0.0:8000)
npm run dev                     # start backend + frontend together (concurrently)
npm run dev:api                 # FastAPI backend only
npm run dev:web                 # Vite frontend only
cd frontend && npm run build      # TypeScript + Vite production build
```

## Architecture
- **`config/`**: `Settings` dataclass (provider, db_url, model), `secrets` (keyring-based), `models` (provider model listing + fuzzy matching)
- **`agents/db_agent.py`**: `get_agent()` builds a `pydantic_ai.Agent[Settings]` singleton with `run_python_code`, `get_schema`, `query_db` tools
- **`tools/db_tools.py`**: three SQLite tools — all connect via `ctx.deps.db_url` (default `sqlite:///scriptordb.sqlite`)
- **`cli/`**: Typer app with `setup`, `forget`, `models`, `ask`, `interactive`, `serve` commands + text-based dispatcher
- **`server/`**: FastAPI app with session-based chat endpoint (SSE streaming), schema endpoint, health check
- **`frontend/`**: separate npm project (React 19 + Vite + TypeScript + HeroUI v3), proxies to the FastAPI backend

## Key quirks
- Package manager is `uv` (use `uv run`, `uv sync`), not pip — the `requirements.txt` is a frozen snapshot
- API keys are stored in the OS keychain via `keyring`, not in `.env` files
- `nim` and `together` providers use `OpenAIChatModel` with a custom `OpenAIProvider(base_url=…)`; other providers use pydantic-ai native models
- Model names use `provider:model_name` prefix format (e.g., `openai:gpt-4o`); `resolve_model()` handles prefixing
- `Settings.db_url` defaults to `sqlite:///scriptordb.sqlite` — the tools strip the `sqlite:///` prefix when connecting
- The `api` directory is gitignored (`fastmcp` is in requirements, but there is no active code in-tree)
- Model list is cached per-provider at `~/.cache/scriptordb/models_<provider>.json` with 1h TTL
- No linter or formatter is configured (no `ruff.toml`, no `mypy.ini`); only `pyright` is set up for IDE use via `pyrightconfig.json`
- Tests use `pydantic_ai.models.test.TestModel` — they never call a real LLM API
