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

### 🔒 Won't Destroy Your Data
Destructive commands (`DROP`, `DELETE`, `ALTER`) are blocked by default. The agent can query and analyze, but it cannot modify or wipe your database unless you explicitly allow it.

---

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Create a workspace for your project
uv run python main.py workspace create /path/to/your/project --name my-project

# 3. Configure your LLM provider and API key
uv run python main.py setup

# 4. Ask your database a question
uv run python main.py ask "show me the top 10 customers by total spend"
```

Launch the web UI:

```bash
npm run dev
```

Backend runs at `http://localhost:8000`. Frontend runs at `http://localhost:5173`.

---

## Works With Any OpenAI-Compatible Provider

OpenAI, Anthropic, Google, Groq, Mistral, OpenRouter, NVIDIA NIM, Together — or any third-party relay with an OpenAI-compatible endpoint. Switch providers in one setting without rewriting prompts.

| Provider | Example model string |
|----------|----------------------|
| OpenAI | `openai:gpt-4o` |
| Anthropic | `anthropic:claude-sonnet-4-20250514` |
| Google | `google:gemini-2.5-pro` |
| Groq | `groq:llama-3.3-70b-versatile` |
| Mistral | `mistral:mistral-large-latest` |
| OpenRouter | `openrouter:anthropic/claude-sonnet-4` |
| NVIDIA NIM | `openai:meta/llama-3.3-70b-instruct` |
| Together | `openai:meta-llama/Llama-3.3-70B-Instruct-Turbo` |

---

## Project Isolation Without the Hassle

Each project gets its own **workspace** — a self-contained configuration that bundles the database path, LLM provider, model, API key, and session history. Manage five SQLite projects at once without worrying about cross-contamination. Switch between them in one command.

---

## What Could Go Wrong — And Why You Don't Have to Worry

| Fear | Plain-English Meaning | How You're Protected |
|------|----------------------|---------------------|
| **AI turns into a backstabber** | A clever prompt tricks it into leaking data or deleting tables | Destructive commands are blocked. All tool calls are logged. |
| **AI formats your hard drive** | It runs code outside its lane and wrecks files | Python execution is restricted to a sandbox. |
| **Your API keys get stolen** | Keys accidentally end up in logs, git, or screenshots | Keys live in the OS keychain. Never in repo files or `.env`. |
| **Locked into one LLM vendor** | You can't switch providers without rewriting everything | `provider:model` naming means one-line swaps. |

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
├── agents/              # Pydantic AI agent + tool registration
├── cli/                 # Typer commands: setup, ask, interactive, serve, workspace
├── config/              # Settings, workspace registry, model resolution, secrets
├── frontend/            # React 19 + Vite + TypeScript + HeroUI
├── server/              # FastAPI routes: chat (SSE), schema, sessions, settings
├── tools/               # SQLite queries, Python sandbox, export, visualization
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
- [ ] Fine-grained permission model per workspace
- [ ] Query result diffing and rollback snapshots
- [ ] Built-in prompt-injection test harness
- [ ] Production deployment template (Docker + reverse proxy)

---

## License

[Apache License 2.0](LICENSE)
