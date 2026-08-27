# ScriptorDB

[![GitHub Stars](https://img.shields.io/github/stars/JunstinLee/scriptordb?style=social)](https://github.com/JunstinLee/ScriptorDB)
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

### 📥 Import CSV & Excel
Read CSV and Excel files and import them directly into the database. All changes can be undone.

### 🛡️ Guardrails Around Writes
Read-only queries run through dedicated read tools. When the agent needs to modify data, it routes through write tools that enforce validation rules:

- `DELETE` and `UPDATE` must include a `WHERE` clause.
- `DROP` operations require `confirm_drop=True`.
- `DROP DATABASE` and dangerous Python patterns (`os.system`, `subprocess`, `eval`, etc.) are rejected.
- Every tool call is logged with a trace ID.
- Write operations are recorded in an undo log and can be reverted.

### 🗄️ MySQL Support

ScriptorDB works with local SQLite files out of the box, but you can also connect to remote MySQL databases with zero configuration overhead.

- **One-click switch** — Open the MySQL config dialog in the sidebar, select MySQL, fill in host/port/user/database/password, and click "Test & Save." The connection is live immediately.
- **Secure credential storage** — MySQL passwords are stored in the OS system keyring, never in workspace files or logs.
- **Seamless switching** — Toggle between SQLite and MySQL at any time. Your MySQL connection details are preserved when you switch back to SQLite.

### 👤 Human Approval for High-Risk Operations
Low-risk writes (CSV/file exports, table creation, DDL, data updates, sandboxed Python) run automatically. Higher-risk operations are paused and surfaced in the web UI for explicit approval before execution:
- Importing large CSV/Excel files (more than 100 rows).
- Applying filters in the browser — you can edit the tool arguments before approving.

You review the pending tool call, choose to approve or deny (optionally editing arguments), and the run resumes on the same stream or cancels accordingly.

### 🌐 Web Crawling — Ask Questions About Any Web Page

Paste a URL, and the agent fetches and analyzes the page content alongside your database. No copy-pasting, no switching tabs.

- **URL + question in one prompt** — Type your question, paste a URL, and the agent crawls the page as Markdown, then answers using both the page content and your database context.
- **Built on crawl4ai** — Pages are rendered and extracted to clean Markdown (up to 50K characters), preserving headings, tables, and text structure.

### Real Browser Automation & Human Takeover
Beyond crawling, the agent can drive a real (visible) Playwright browser — navigate, click, fill forms, extract tables and links, manage cookies and login profiles — and answer questions about live pages.

- **Visible browser with saved profiles** — Cookie sets and full login profiles (including multi-origin localStorage) are stored in your OS keyring and can be restored later.
- **Interactive tooling** — The agent can navigate, click, type, scroll, screenshot, read page structure, and apply filters to JavaScript-driven tables.
- **Human takeover when it matters** — Captcha, MFA, OAuth logins, and antibot walls are detected automatically; the agent pauses and hands control to you, then resumes the same run with your actions injected once you hand control back.
- **Live viewport** — The browser screen streams to the web UI over WebRTC (with a screenshot fallback), so you can watch every step.

### 🔍 Search Session History
Session history is searchable so you can quickly find past questions and results across long-running conversations.

### ↩️ Undo & Session History
Every run that changes data is grouped into an undo log. From the CLI or the web UI you can list those groups and revert the database to a previous state. Reverting replays the recorded undo statements in reverse order across the affected runs. Sessions persist per workspace (JSON under `<workspace>/.scriptordb/sessions/`), so you can close the app and pick up where you left off.

### 📁 Workspace Isolation Out Of The Box
Every project lives in its own workspace — a self-contained bundle of database path, LLM provider, model, API key, and session history. Run five SQLite projects side by side and switch between them with one command. The agent only ever sees the active workspace's database, so nothing crosses the line.

---

## Quick Start

```bash
uv sync                              # backend
npm install                          # concurrently
cd frontend && npm install && cd ..  # UI

npm run dev
```

That's it. Backend at `http://localhost:8000`, UI at `http://localhost:5173`. Create workspaces, plug in your API key, and start asking — all from the web interface. Your API key is stored in the OS keychain, never in repo files. The CLI can do the same: `uv run python main.py setup` walks through provider + key, then `uv run python main.py workspace create /path/to/project`. Run `uv run python main.py --help` for the full command list.

---

## Works With Any OpenAI-Compatible Provider

Four providers are built in — OpenRouter, NVIDIA NIM, Together, and DeepSeek — each mapped to its own OpenAI-compatible endpoint. A `provider:model` naming scheme means switching providers is a one-setting change, and any custom OpenAI-compatible relay can be added the same way.

| Provider | Example model string |
|----------|----------------------|
| OpenRouter | `openrouter:claude-sonnet-4-6` |
| NVIDIA NIM | `openai:moonshotai/kimi-k2.6` |
| Together | `openai:gpt-5.5` |
| DeepSeek | `openai:deepseek-v4-pro` |

Use `uv run python main.py models` to see the live model list for a provider, or pass a substring like `--model gpt-5.5` and the agent will fuzzy-match it.

---

## What Could Go Wrong — And Why You Don't Have to Worry

| Fear | Plain-English Meaning | How You're Protected |
|------|----------------------|---------------------|
| **AI turns into a backstabber** | A clever prompt tricks it into leaking data or deleting tables | Read/write tools are separate; validators reject dangerous SQL/DDL. All tool calls are logged. |
| **AI formats your hard drive** | It runs code outside its lane and wrecks files | Python execution is restricted to a sandbox (import whitelist, CPU/memory limits) and dangerous patterns are blocked. File tools and downloads stay inside the workspace outputs directory; sandbox results land in `<workspace>/result/`. |
| **Your API keys get stolen** | Keys accidentally end up in logs, git, or screenshots | Keys live in the OS keychain. Never in repo files or `.env`. |
| **Locked into one LLM vendor** | You can't switch providers without rewriting everything | `provider:model` naming means one-line swaps. |
| **You can't take back a bad change** | The agent modifies data and you need to recover | Every write run is recorded in an undo log and can be reverted from the CLI or web UI. |

---
🤝 Commercial Partners / API Providers Wanted （Hasn't started yet）

ScriptorDB is designed to route users to API providers and relays. If you operate a stable API relay, token-resale platform, or self-hosted model endpoint, we are open to revenue-sharing partnerships. 

Email: justinlee@aivault.dev

---

## Architecture

```
ScriptorDB/
├── agents/              # Pydantic AI agent builder, audit/undo capabilities, agent cache
├── api/                 # FastAPI app + routers: chat (SSE), approve, schema, models, settings, files, undo, history, browser_* (incl. WebRTC viewport WebSocket)
├── browser/             # Playwright browser lifecycle, profiles, login-state detection, human-takeover state machine
├── cli/                 # Typer commands: setup, ask, interactive, serve, workspace, undo
├── config/              # Settings, workspace registry, model resolution, secrets/keyring, provider config
├── core/                # Logging setup and stdout/stderr file logging
├── database/            # MySQL connection pool (pymysql) + SQLAlchemy repository layer
├── frontend/            # React 19 + Vite + TypeScript + HeroUI + Tailwind CSS v4
├── runtime/             # Agent run pipeline, approval orchestration, session persistence, tool middleware
├── schemas/             # Pydantic DTOs (tool results, SSE events, sessions)
├── scripts/             # Standalone diagnostic tools (browser stream, viewport, layout)
├── services/            # Business service layer (chat, undo, mysql, workspace, history, ...)
├── tools/               # Tool registry + tools: SQL, validators, sandbox, import/export, viz, crawl, download, browser filters, undo log
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
- [x] Session persistence per workspace
- [x] Undo log for write operations
- [x] MySQL support (connection pool + keyring credentials)
- [x] Web crawling (crawl4ai) and document download
- [x] Browser automation with human takeover and WebRTC viewport
- [x] Searchable session history
- [ ] Session expiration / cleanup (24h TTL planned)
- [ ] Fine-grained permission model per workspace
- [ ] Query result diffing and rollback snapshots
- [ ] Built-in prompt-injection test harness
---

## License

[Apache License 2.0](LICENSE)
