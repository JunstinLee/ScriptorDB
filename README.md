# ScriptorDB

[![GitHub Stars](https://img.shields.io/github/stars/yourname/scriptordb?style=social)](https://github.com/yourname/scriptordb)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

**An AI agent that reads your SQLite database and answers questions in plain English.** No SQL required. No schema docs to write. Just point it at your `.sqlite` file and start asking.

![Demo GIF](TODO: add demo gif here)

---

## What The Agent Actually Does

### 🔍 Reads Your Schema So You Don't Have To
The agent inspects your database structure automatically. You never need to paste `CREATE TABLE` statements or explain your column names. It knows your tables, columns, types, and foreign keys before it writes a single query.

### 💬 Answers Follow-Up Questions
This isn't a one-shot SQL generator. The agent remembers context across your conversation. Ask "top customers," then "what did they buy," then "plot a monthly trend" — it maintains state and builds on previous answers.

### 🧠 Writes SQL, Runs It, Explains Results
You ask in English. The agent:
1. Reads the relevant schema
2. Generates the correct SQL
3. Executes it safely
4. Returns a human-readable answer — not just a raw table dump

```
You: "Which products had revenue drop last quarter?"
Agent: "Based on your orders and products tables, here are the 3 products
        with declining Q-over-Q revenue..."
```

### 📊 Analyzes & Visualizes Data
Beyond SQL, the agent can run Python code in a sandbox to compute statistics, generate charts with matplotlib, or export results to Excel — all from natural language requests.

### 🛡️ Guardrails Around Writes
Read-only queries run through dedicated read tools. When the agent needs to modify data, it routes through write tools that enforce validation rules:

- `DELETE` and `UPDATE` must include a `WHERE` clause.
- `DROP` operations require `confirm_drop=True`.
- `DROP DATABASE` and dangerous Python patterns (`os.system`, `subprocess`, `eval`, etc.) are rejected.
- Every tool call is logged with a trace ID.
- Write operations are recorded in an undo log and can be reverted.

### ↩️ Undo & Session History
Every run that changes data is grouped into an undo log. From the CLI or the web UI you can list those groups and revert the database to a previous state. Sessions persist with a 24-hour TTL, so you can close the app and pick up where you left off.

---

## Quick Start

```bash
# 1. Install backend dependencies
uv sync

# 2. Create a workspace for your project
uv run python main.py workspace create /path/to/your/project --name my-project

# 3. Configure your LLM provider and API key
uv run python main.py setup

# 4. Ask your database a question
uv run python main.py ask "show me the top 10 customers by total spend"
```

Run with no arguments to open the interactive menu:

```bash
uv run python main.py
```

Launch the web UI:

```bash
npm install                 # root installs concurrently
npm install --prefix frontend
npm run dev
```

Backend runs at `http://localhost:8000`. Frontend runs at `http://localhost:5173`.

---

## Everyday CLI Commands

```bash
# Workspace management
uv run python main.py workspace list
uv run python main.py workspace switch <id_or_name>
uv run python main.py workspace current
uv run python main.py workspace rename <id_or_name> <new_name>
uv run python main.py workspace remove <id_or_name> [--delete-files]

# Provider / model management
uv run python main.py setup
uv run python main.py forget
uv run python main.py models --provider openai

# Query modes
uv run python main.py ask "..."
uv run python main.py interactive

# Server
uv run python main.py serve [--host 0.0.0.0] [--port 8000]

# Undo
uv run python main.py undo list
uv run python main.py undo revert <group_id>
```

---

## Works With Any OpenAI-Compatible Provider

OpenAI, Anthropic, Google, Groq, Mistral, OpenRouter, NVIDIA NIM, Together — or any third-party relay with an OpenAI-compatible endpoint. Switch providers in one setting without rewriting prompts.

| Provider | Example model string |
|----------|----------------------|
| OpenAI | `openai:gpt-5.5` |
| Anthropic | `anthropic:claude-sonnet-4-6` |
| Google | `google:gemini-3.5-flash` |
| Groq | `groq:kimi-2.6` |
| Mistral | `mistral:mistral-medium-3.5` |
| OpenRouter | `openrouter:deepseek-v4-pro` |
| NVIDIA NIM | `openai:kimi-k2.6` |
| Together | `openai:gpt-5.5` |

Use `uv run python main.py models` to see the live model list for a provider, or pass a substring like `--model gpt-5.5` and the agent will fuzzy-match it.

---

## Project Isolation Without the Hassle

Each project gets its own **workspace** — a self-contained configuration that bundles the database path, LLM provider, model, API key, and session history. Manage five SQLite projects at once without worrying about cross-contamination. Switch between them in one command.

---

## What Could Go Wrong — And Why You Don't Have to Worry

| Fear | Plain-English Meaning | How You're Protected |
|------|----------------------|---------------------|
| **AI turns into a backstabber** | A clever prompt tricks it into leaking data or deleting tables | Read/write tools are separate; validators reject dangerous SQL/DDL. All tool calls are logged. |
| **AI formats your hard drive** | It runs code outside its lane and wrecks files | Python execution is restricted to a sandbox and dangerous patterns are blocked. File paths cannot escape the workspace outputs directory. |
| **Your API keys get stolen** | Keys accidentally end up in logs, git, or screenshots | Keys live in the OS keychain. Never in repo files or `.env`. |
| **Locked into one LLM vendor** | You can't switch providers without rewriting everything | `provider:model` naming means one-line swaps. |
| **You can't take back a bad change** | The agent modifies data and you need to recover | Every write run is recorded in an undo log and can be reverted from the CLI or web UI. |

---

## 🤝 Commercial Partners / API Providers Wanted

ScriptorDB is designed to route users to API providers and relays. If you operate a stable API relay, token-resale platform, or self-hosted model endpoint, we are open to revenue-sharing partnerships.

- Telegram: `@your_telegram_handle`
- WeChat: `your_wechat_id`
- Email: `partnerships@yourdomain.com`

---

## Architecture

```
ScriptorDB/
├── agents/              # Pydantic AI agent, toolsets, audit/undo hooks
├── cli/                 # Typer commands: setup, ask, interactive, serve, workspace, undo
├── config/              # Settings, workspace registry, model resolution, secrets, global defaults
├── frontend/            # React 19 + Vite + TypeScript + HeroUI + Tailwind CSS v4
├── server/              # FastAPI app + routers: chat (SSE), sessions, schema, models, settings, files, undo
├── tools/               # SQLite queries, DDL/DML validators, Python sandbox, export, visualization, undo log
├── tests/               # pytest suite using TestModel (zero real LLM calls)
├── main.py              # Entry point: no args → menu; args → Typer CLI
├── pyproject.toml       # uv project config
└── package.json         # Concurrent dev scripts for backend + frontend
```

---

## Roadmap

- [x] Multi-provider LLM agent with SQLite tools
- [x] Workspace-based config and key isolation
- [x] CLI, FastAPI backend, and React frontend
- [x] Session persistence with TTL
- [x] Undo log for write operations
- [ ] Fine-grained permission model per workspace
- [ ] Query result diffing and rollback snapshots
- [ ] Built-in prompt-injection test harness
- [ ] Production deployment template (Docker + reverse proxy)

---

## License

[Apache License 2.0](LICENSE)
