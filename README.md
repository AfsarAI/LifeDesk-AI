# LifeDesk AI — MiniTask Agent (Day 1)

A minimal FastAPI backend that connects to the Google Gemini API (`google-genai` SDK using the Interactions API) and safely executes an explicitly registered `create_task` tool against an in-memory task list.

## Project Structure

- `main.py` — FastAPI application and HTTP endpoints (`/health`, `/tasks`, `/chat`).
- `agent.py` — `MiniTaskAgent` loop that calls Gemini, enforces iteration limits, and sends tool results back.
- `tools.py` — In-memory task store, `create_task` Python implementation, Gemini declaration, and `TOOL_REGISTRY`.
- `schemas.py` — Pydantic models for API requests/responses and strict tool argument validation.
- `config.py` — Environment configuration loader (`.env` via `python-dotenv`).
- `requirements.txt` — Python dependencies.
- `.env.example` — Environment variable template (safe to commit; never commit `.env`).

## Setup & Run

1. Create and activate a virtual environment, then install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure your Gemini API key locally:
   ```bash
   cp .env.example .env
   # Edit .env and set GEMINI_API_KEY=your_real_key
   ```

3. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

4. Open Swagger UI in your browser:
   - `http://127.0.0.1:8000/docs`

## Testing Endpoints

1. `GET /tasks` — Initially returns `{"tasks": [], "count": 0}`.
2. `POST /chat` — Send:
   ```json
   {
     "message": "Remind me to submit the Q4 report by 2026-11-30"
   }
   ```
3. `GET /tasks` — Verify the new task with a generated `id` appears in the list.

Run the automated test suite:
```bash
pytest
```
