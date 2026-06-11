# AGENTS.md

## Quick commands
```bash
uv run pytest tests/          # all tests (pytest + pytest-asyncio, auto mode)
uv run python main.py         # interactive dispatcher (no args = dispatcher)
uv run python main.py setup   # configure provider + API key
uv run python main.py ask "query"  # single-shot query
```

## Architecture
- **`config/`**: `Settings` dataclass (provider, db_url, model), `secrets` (keyring-based, not `.env`), `models` (provider model listing + fuzzy matching)
- **`agents/db_agent.py`**: `get_agent()` builds a `pydantic_ai.Agent[Settings]` singleton with `run_python_code`, `get_schema`, `query_db` tools
- **`tools/db_tools.py`**: three SQLite tools — all connect via `ctx.deps.db_url` (default `sqlite:///scriptordb.sqlite`)
- **`cli/`**: Typer app with `setup`, `forget`, `models`, `ask`, `interactive`, `serve` commands + text-based dispatcher

## Key quirks
- API keys are stored in the OS keychain via `keyring`, not in `.env` files
- `nim` and `together` providers use `OpenAIChatModel` with a custom `OpenAIProvider(base_url=…)` instead of pydantic-ai's native provider
- Model names use `provider:model_name` prefix format (e.g., `openai:gpt-4o`); `resolve_model()` handles prefixing
- `Settings.db_url` defaults to `sqlite:///scriptordb.sqlite` — the tools strip the `sqlite:///` prefix when connecting
- The `api` directory is gitignored — likely a separate FastMCP/HTTP server that wraps the same agent (not yet built out in this repo)
- Model list is cached per-provider at `~/.cache/scriptordb/models_<provider>.json` with 1h TTL
