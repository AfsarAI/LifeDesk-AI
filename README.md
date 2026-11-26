# LifeDesk AI — Your Personal AI Chief of Staff

> **Project Status:** Active local development (`v0.2.0`). Designed for single-node local usage and iterative feature testing.

LifeDesk AI is a full-stack personal AI assistant that combines persistent task/memory management, Gmail and Google Calendar integrations via the **Model Context Protocol (MCP)**, multi-tool agent orchestration, human-in-the-loop approval cards, and a modern Markdown-powered React chat interface.

---

## Key Features

- **Unified Hybrid Tooling (Native + MCP):**
  - **11 Native Tools** backed by SQLite: `create_task`, `list_tasks`, `update_task`, `complete_task`, `search_tasks`, `save_memory`, `retrieve_memory`, `create_reminder`, `list_reminders`, `get_user_preferences`, and `request_user_approval`.
  - **14 MCP Tools** executed via isolated per-user STDIO MCP servers (`gmail_server.py` and `calendar_server.py`): Gmail search/read/thread/draft/send and Google Calendar list/availability/conflict-check/create/update/delete.
- **Sequential Multi-Tool Loop & Multi-Action Staging:**
  - `LifeDeskAgent` supports chained native + MCP tool calls in a single turn (default `MAX_TOOL_ITERATIONS=8`, configurable up to `15`) so read checks (such as calendar conflict lookup) and multiple proposed external actions (such as creating an event **and** proposing an email) complete together without dropping later actions.
- **Human-in-the-Loop Approval Cards:**
  - Sensitive external mutations (`gmail_send_email`, `calendar_create_event`, `calendar_update_event`, `calendar_delete_event`) never run automatically.
  - Each action stages a structured `PENDING` approval card directly inline in the chat turn with human-readable fields (`Approve` / `Approve and Send`, `Edit Draft` for emails, and `Reject`), transitioning cleanly to resolved status pills (`Executed` / `Rejected`) once acted upon.
- **Rich Chat Markdown Preview (`MarkdownMessage`):**
  - Assistant responses render formatted GFM tables (supporting multi-line `<br>` cell breaks cleanly without raw HTML injection), headings, lists, blockquotes, syntax-highlighted code blocks with a one-click **Copy** button, and safe responsive images.
- **Google OAuth 2.0 (Authorization Code + PKCE):**
  - CSRF-protected one-time `state` + `S256` PKCE verifier, least-privilege scopes, automatic token refresh, and Fernet encryption at rest (`TOKEN_ENCRYPTION_KEY`) isolated per user.
- **Provider Switching & Timezone Support:**
  - Switch between **Groq** (`openai/gpt-oss-20b`) and **OpenRouter** (`openrouter/free`) via `backend/.env` without changing agent logic.
  - Supports IANA user timezones (`USER_TIMEZONE` in `backend/.env` or updated live in **Settings**).

---

## Technology Stack & What Each Piece Does

### Backend (`/backend`)

| Technology / Package | Version | Used For |
|---|---|---|
| **Python** | `3.12` | Core backend runtime and STDIO MCP subprocesses |
| **FastAPI** | `0.165.0` | REST API (`/api/chat`, `/api/tasks`, `/api/memories`, `/api/approvals`, `/api/integrations/*`, `/api/auth/*`, `/api/health`) and automatic Swagger UI (`/docs`) |
| **Uvicorn** | `0.54.0` | ASGI development server with hot-reload (`--reload`) |
| **Pydantic** | `2.14.4` | Request/response schemas, `.env` settings validation, and strict tool argument validation |
| **SQLAlchemy + SQLite** | `2.1.9` / `lifedesk.db` | Persistent storage for users, tasks, memories, reminders, conversations, messages, approvals, tool audit logs, OAuth states, and encrypted Google tokens |
| **OpenAI Python SDK** | `3.59.0` | Unified Chat Completions + tool-calling client targeting Groq (`https://api.groq.com/openai/v1`) and OpenRouter (`https://openrouter.ai/api/v1`) |
| **Official MCP SDK (`mcp`)** | `2.3.0` | STDIO client (`stdio_client`, `ClientSession`) and local MCP tool servers (`gmail_server.py`, `calendar_server.py`) |
| **Google API Client & Auth** | `google-api-python-client 2.202.0`, `google-auth 2.63.1`, `google-auth-oauthlib 1.5.0`, `httpx 0.28.1` | OAuth 2.0 + PKCE token exchange/refresh and Gmail / Google Calendar API calls |
| **Cryptography (`Fernet`)** | `50.0.2` | Symmetric encryption of stored Google access/refresh tokens at rest (`TokenCipher`) |
| **python-dotenv** | `1.2.4` | Loading environment variables from `backend/.env` |
| **Pytest** | `9.2.0` | Backend unit, security, OAuth, MCP STDIO, and multi-tool workflow tests |

### Frontend (`/frontend`)

| Technology / Package | Version | Used For |
|---|---|---|
| **React + React DOM** | `^19.0.0` | Component-driven UI across Chat, Tasks, Memory, Integrations, and Settings views |
| **TypeScript** | `^5.7.2` | End-to-end static typing for API payloads, approvals, and React components |
| **Vite** | `^6.0.0` | Fast local HMR dev server (`localhost:5173`) and production bundler |
| **Tailwind CSS** | `^4.0.0` (`@tailwindcss/vite`) | Dark-mode UI styling, responsive layout, approval cards, and code/table styling |
| **Lucide React** | `^0.469.0` | Crisp UI icons across navigation, tool status pills, approval cards, and copy controls |
| **react-markdown** | `^10.1.0` | Safe React-tree Markdown rendering (no `dangerouslySetInnerHTML`) |
| **remark-gfm** | `^4.0.1` | GitHub Flavored Markdown tables, task lists, strikethrough, and autolinks |
| **rehype-highlight** | `^7.0.2` | Syntax highlighting for fenced code blocks inside assistant responses |

---

## Architecture & Project Structure

```text
React Frontend (Vite + Tailwind, http://localhost:5173)
        │  HTTP JSON + Bearer Session Token (/api/*)
        ▼
FastAPI Backend (http://127.0.0.1:8000)
  ├── /api/auth, /api/tasks, /api/memories, /api/conversations, /api/health
  ├── /api/integrations/google/*  ──▶ Google OAuth 2.0 + Fernet TokenCipher
  ├── /api/approvals/*            ──▶ ApprovalService (PENDING -> EXECUTED / REJECTED)
  └── /api/chat                   ──▶ LifeDeskAgent (default max 8 iterations)
                                         │
                                  UnifiedToolExecutor
                                    ├── Native Tools  ──▶ SQLite (SQLAlchemy)
                                    └── MCP Client    ──▶ STDIO MCP Servers
                                                            ├── gmail_server.py    ──▶ Gmail API
                                                            └── calendar_server.py ──▶ Calendar API
```

```text
LifeDesk-AI/
├── backend/
│   ├── app/
│   │   ├── agent/          # LifeDeskAgent loop, LLMProvider, native tool_registry, unified_tools
│   │   ├── api/routes/     # FastAPI routers (chat, approvals, auth, tasks, memories, integrations, health)
│   │   ├── approvals/      # ApprovalService lifecycle & execution gates
│   │   ├── database/       # SQLAlchemy models, SQLite init/migrations, user-scoped repositories
│   │   ├── integrations/   # Google OAuth 2.0 + PKCE service
│   │   ├── mcp_client/     # STDIO MCPClientManager launching Gmail & Calendar servers
│   │   ├── mcp_servers/    # Isolated MCP servers & Google API wrappers
│   │   ├── schemas/        # Pydantic request/response & tool schemas
│   │   ├── security/       # TokenCipher (Fernet), signed session tokens, rate limiter
│   │   └── tools/          # Native internal tool implementations
│   ├── tests/              # Pytest suite (agent, API, MCP, OAuth, provider, tools, workflows)
│   ├── .env.example        # Environment template (copy to backend/.env)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # Sidebar, ContextPanel, ApprovalCard, ToolCallList, MarkdownMessage
│   │   ├── hooks/          # useLifeDeskData central state & refresh hooks
│   │   ├── pages/          # ChatPage, TasksPage, MemoryPage, IntegrationsPage, SettingsPage
│   │   ├── services/       # Typed apiClient
│   │   └── types/          # TypeScript interfaces mirroring backend schemas
│   └── package.json
└── docs/                   # Architecture, OAuth setup, MCP guide, Security, Roadmap
```

Deep-dive documentation:
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/OAUTH_SETUP.md](docs/OAUTH_SETUP.md)
- [docs/MCP_GUIDE.md](docs/MCP_GUIDE.md)
- [docs/AGENT_WORKFLOWS.md](docs/AGENT_WORKFLOWS.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)

---

## How to Run Locally (Development Setup)

### Prerequisites
- **Python 3.12+**
- **Node.js 18+ & npm**
- A **Groq API key** (or **OpenRouter API key**)
- *(Optional for live Gmail/Calendar)* Google Cloud OAuth 2.0 Client ID & Secret — or set `DEMO_MODE=true` to test tool flows with sample Gmail/Calendar data.

### 1. Clone & Set Up Python Virtual Environment
```bash
git clone https://github.com/AfsarAI/LifeDesk-AI.git
cd LifeDesk-AI
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Generate Keys & Configure `backend/.env`
Generate a Fernet encryption key (required for storing OAuth tokens) and an optional stable session secret (recommended so browser sessions survive `--reload` restarts):
```bash
python3 -c "from cryptography.fernet import Fernet; print('TOKEN_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
python3 -c "import secrets; print('APP_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

Create `backend/.env` from the template:
```bash
cp backend/.env.example backend/.env
```
Edit `backend/.env`:
- **LLM provider:** set `LLM_PROVIDER=groq` and `GROQ_API_KEY=...` (or `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY=...`).
- **Encryption & session keys:** paste `TOKEN_ENCRYPTION_KEY=...` and `APP_SECRET_KEY=...`.
- **Google OAuth (live integration):** set `GOOGLE_CLIENT_ID=...` and `GOOGLE_CLIENT_SECRET=...` (see [docs/OAUTH_SETUP.md](docs/OAUTH_SETUP.md)), **or** set `DEMO_MODE=true` if testing without Google Cloud credentials.
- **Timezone & agent loop:** set `USER_TIMEZONE=Asia/Kolkata` (or your IANA timezone) and `MAX_TOOL_ITERATIONS=8`.

### 3. Start the Backend Server (Terminal 1)
From the `backend/` directory (so SQLite creates `backend/lifedesk.db` cleanly):
```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Backend health check: `http://127.0.0.1:8000/api/health`
- Interactive Swagger API docs: `http://127.0.0.1:8000/docs`

### 4. Start the Frontend Dev Server (Terminal 2)
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## How to Test Locally

### 1. Backend Automated Tests (`pytest`)
Run the full backend test suite (uses isolated temp SQLite databases, mocked LLM/HTTP clients, and real STDIO MCP process tests—no real emails sent):
```bash
cd backend
../.venv/bin/pytest -v
```
Test modules in `backend/tests/`:
- `test_agent.py` — multi-tool loop, unknown/malformed tool rejection, max-iteration guard
- `test_api.py` — `/api/health`, Tasks CRUD, Memory CRUD, Chat & Conversations endpoints
- `test_provider.py` — Groq/OpenRouter switching, error mapping, secret redaction
- `test_tools.py` — native task & memory tool lifecycle
- `test_oauth.py` — Fernet encryption round-trip, PKCE/state validation, token refresh & disconnect
- `test_mcp_gmail_calendar.py` — STDIO MCP tool discovery, Gmail reply threading (`thread_id` / `in_reply_to`), Calendar conflict & timezone handling
- `test_workflows_and_security.py` — multi-user isolation, SQLite migration, sequential multi-action approval staging, nullable schemas, timezone persistence

### 2. Frontend Type-Check & Production Build
Verify TypeScript types (`tsc -b`) and Vite production bundling:
```bash
cd frontend
npm run build
```

### 3. Quick Manual UI Smoke Test (`http://localhost:5173`)
1. Open **Settings** -> verify LLM status is configured (`GROQ` / `OPENROUTER`), database is `ok`, and test changing **Calendar Timezone** (updates the sidebar footer immediately).
2. Open **Integrations** -> verify Google OAuth connection status (`Connect Gmail` / `Connect Google Calendar` if live OAuth is configured).
3. Open **Tasks** & **Memory** -> create, complete/update, reload the browser tab to verify SQLite persistence, and delete test entries.
4. Open **Chat** -> test:
   - Read-only multi-tool query: *"List my pending tasks and check my calendar for today."*
   - Multi-action approval flow: propose scheduling a meeting and sending a test email, verify **both** inline approval cards render, inspect `Edit Draft`, and click **Reject** if you do not want to execute live external writes.
   - Markdown preview: confirm tables, `<br>` cell breaks, headings, lists, and code blocks with the **Copy** button render cleanly.

---

## Current Limitations (Development Phase)

- SQLite is intended for local single-node development; production deployments should migrate to PostgreSQL (see [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md)).
- `ALLOW_DEMO_USER_FALLBACK=true` simplifies local development by defaulting unauthenticated requests to local Demo User `#1`; set `false` in production and pair `/api/auth/*` with real authentication.
- If `APP_SECRET_KEY` is omitted from `backend/.env`, an ephemeral signing key is generated per process—re-select your user in **Settings** if an open browser tab hits a `401` after `uvicorn --reload` restarts.
- Google Cloud projects in **Testing** mode issue refresh tokens that expire after 7 days and allow up to 100 test users until OAuth verification is completed.
- Google Drive, Web Search, Browser Automation, Notion, and Slack are currently **Coming Soon** architectural placeholders.
