# LifeDesk AI — Personal AI Agent (Days 1–4)

LifeDesk AI is a full-stack personal productivity AI agent built with **FastAPI**, **SQLAlchemy + SQLite**, the **OpenAI Python SDK** (supporting **Groq** and **OpenRouter**), and a **React + TypeScript + Vite + Tailwind CSS** web interface.

## Project Structure

```text
LifeDesk-AI/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint, lifespan DB init, CORS
│   │   ├── config.py                # Env configuration (Groq, OpenRouter, SQLite)
│   │   ├── api/routes/              # /api/chat, /api/tasks, /api/memories, /api/conversations, /api/health
│   │   ├── agent/                   # LLMProvider, ToolRegistry, LifeDeskAgent loop
│   │   ├── tools/                   # 7 validated task & memory tools
│   │   ├── database/                # SQLAlchemy engine, ORM models, repositories
│   │   └── schemas/                 # Pydantic v2 request/response/tool schemas
│   ├── tests/                       # Backend unit & integration tests (pytest)
│   ├── pytest.ini
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/              # Sidebar, ContextPanel, ToolCallList
│   │   ├── pages/                   # ChatPage, TasksPage, MemoryPage, SettingsPage
│   │   ├── hooks/                   # useLifeDeskData
│   │   ├── services/                # Centralized apiClient
│   │   ├── types/                   # TypeScript API types
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Setup & Running Locally

### 1. Backend (`http://127.0.0.1:8000`)

```bash
cd backend
cp .env.example .env
# Edit .env and add GROQ_API_KEY (or OPENROUTER_API_KEY and set LLM_PROVIDER=openrouter)
```

Using the project virtual environment (or create one inside `backend/`):
```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Or in a fresh venv:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend (`http://localhost:5173`)

In a second terminal:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Switching LLM Providers (Groq ↔ OpenRouter)

Edit `backend/.env` without modifying any code:
- **Groq (default):**
  ```env
  LLM_PROVIDER=groq
  GROQ_API_KEY=your_groq_key
  GROQ_MODEL=openai/gpt-oss-20b
  ```
- **OpenRouter:**
  ```env
  LLM_PROVIDER=openrouter
  OPENROUTER_API_KEY=your_openrouter_key
  OPENROUTER_MODEL=openrouter/free
  ```
Restart `uvicorn` after editing `.env`.

## Running Tests

```bash
cd backend
../.venv/bin/pytest -v
```
