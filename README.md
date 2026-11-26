# LifeDesk AI — Your Personal AI Chief of Staff

LifeDesk AI is a full-stack personal AI assistant built with **FastAPI**, **SQLAlchemy + SQLite**, the **OpenAI Python SDK** (**Groq** / **OpenRouter**), the **official Model Context Protocol (MCP) Python SDK (`mcp==2.3.0`)**, **Google OAuth 2.0**, and a **React + TypeScript + Vite + Tailwind CSS** web interface.

---

## Key Features

- **Unified Hybrid Tooling (Native + MCP):**
  - **11 Native Tools** for internal state: `create_task`, `list_tasks`, `update_task`, `complete_task`, `search_tasks`, `save_memory`, `retrieve_memory`, `create_reminder`, `list_reminders`, `get_user_preferences`, and `request_user_approval`.
  - **14 MCP Tools** via isolated per-user STDIO MCP servers (`lifedesk-gmail` and `lifedesk-calendar`): Gmail search/read/thread/draft/send and Google Calendar list/availability/conflict-check/create/update/delete.
- **Google OAuth 2.0 Authorization Code + PKCE Flow:**
  - CSRF-protected one-time `state` + `S256` PKCE verifier.
  - Least-privilege scopes with incremental authorization and offline refresh tokens.
  - Fernet-encrypted token storage at rest (`TOKEN_ENCRYPTION_KEY`) scoped per LifeDesk user.
- **Human-in-the-Loop Approval System:**
  - Sending emails (`gmail_send_email`) and creating/updating/deleting calendar events (`calendar_create_event`, `calendar_update_event`, `calendar_delete_event`) **never execute automatically**—they stage a `PENDING` approval card in the React UI and require explicit user confirmation.
- **Agentic Workflows:**
  - Email-to-calendar scheduling with conflict detection, daily briefings, context-aware Gmail draft replies, and free-slot task scheduling.
- **LLM Provider Switching:**
  - Switch between **Groq** (`openai/gpt-oss-20b`) and **OpenRouter** (`openrouter/free`) via `backend/.env` without modifying agent or tool code.
- **Multi-User Isolation Foundation:**
  - Signed LifeDesk session tokens (`Authorization: Bearer ...`) keep LifeDesk authentication separate from Google OAuth, scoping tasks, memories, conversations, approvals, and Google credentials by `user_id` (with optional `ALLOW_DEMO_USER_FALLBACK=true` for single-user local dev).

---

## Architecture Overview

```text
React Frontend (Vite + Tailwind, localhost:5173)
        │  HTTP JSON + Bearer Session Token (/api/*)
        ▼
FastAPI Backend (127.0.0.1:8000)
  ├── /api/auth, /api/tasks, /api/memories, /api/conversations, /api/health
  ├── /api/integrations/google/*  ──▶ Google OAuth 2.0 + Fernet TokenCipher
  ├── /api/approvals/*            ──▶ ApprovalService (PENDING -> APPROVED -> EXECUTED)
  └── /api/chat                   ──▶ LifeDeskAgent (max 5 iterations)
                                         │
                                  UnifiedToolExecutor
                                    ├── Native Tools  ──▶ SQLite (SQLAlchemy)
                                    └── MCP Client    ──▶ STDIO MCP Servers
                                                            ├── gmail_server.py    ──▶ Gmail API
                                                            └── calendar_server.py ──▶ Calendar API
```

Deep-dive docs:
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/OAUTH_SETUP.md](docs/OAUTH_SETUP.md)
- [docs/MCP_GUIDE.md](docs/MCP_GUIDE.md)
- [docs/AGENT_WORKFLOWS.md](docs/AGENT_WORKFLOWS.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.12, FastAPI `0.165.0`, Pydantic `2.14.4`, Uvicorn `0.54.0` |
| Database | SQLAlchemy `2.1.9`, SQLite (`lifedesk.db`) |
| LLM Client | OpenAI Python SDK `3.59.0` (Groq & OpenRouter endpoints) |
| External Tools | Official MCP SDK `mcp==2.3.0` (`MCPServer`, `stdio_client`, `ClientSession`) |
| Google APIs & Security | `google-api-python-client==2.202.0`, `cryptography==50.0.2` (Fernet), `httpx==0.28.1` |
| Frontend | React 19, TypeScript, Vite 6, Tailwind CSS 4, `lucide-react` |

---

## Local Setup

### 1. Generate a Token Encryption Key
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Configure Backend Environment
```bash
cd backend
cp .env.example .env
```
Edit `backend/.env` and configure:
- `LLM_PROVIDER=groq` + `GROQ_API_KEY=...` (or `LLM_PROVIDER=openrouter` + `OPENROUTER_API_KEY=...`)
- `GOOGLE_CLIENT_ID=...` and `GOOGLE_CLIENT_SECRET=...` (see [docs/OAUTH_SETUP.md](docs/OAUTH_SETUP.md))
- `TOKEN_ENCRYPTION_KEY=<generated-fernet-key>`
- Optional `USER_TIMEZONE=Asia/Kolkata` (or set it in the Settings UI)

### 3. Install & Start Backend (`http://127.0.0.1:8000`)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
*(Or using the workspace root `.venv`: `cd backend && ../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.)*

### 4. Install & Start Frontend (`http://localhost:5173`)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Swagger API docs are also available at `http://127.0.0.1:8000/docs`.

---

## Running Automated Tests

```bash
cd backend
../.venv/bin/pytest -v
```
Frontend type-check & production build:
```bash
cd frontend
npm run build
```

---

## Current Limitations

- SQLite is intended for local single-node development; production deployments should migrate to PostgreSQL (see [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md)).
- `ALLOW_DEMO_USER_FALLBACK=true` simplifies local development by defaulting unauthenticated requests to local Demo User `#1`; disable it (`false`) in production and pair `/api/auth/*` with password/SSO verification.
- Google Cloud projects in **Testing** mode issue refresh tokens that expire after 7 days and allow up to 100 test users until OAuth verification is completed.
- Google Drive, Web Search, Browser Automation, Notion, and Slack are currently **Coming Soon** architectural placeholders.
