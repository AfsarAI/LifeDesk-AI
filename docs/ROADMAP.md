# LifeDesk AI Roadmap

This roadmap tracks what is **implemented and verified**, **partially implemented**, and **planned** for future milestones.

---

## Implemented (Days 1–7)

- **Core Backend & Database:** FastAPI + Pydantic v2 + SQLAlchemy 2.x + SQLite with non-destructive migrations (`users`, `tasks`, `reminders`, `conversations`, `messages`, `memories`, `integrations`, `integration_credentials`, `oauth_states`, `approvals`, `tool_executions`).
- **LLM Provider Abstraction:** Groq (`openai/gpt-oss-20b`) and OpenRouter (`openrouter/free`) via OpenAI Python SDK with explicit error mapping and no silent paid-model fallback.
- **Native Tools (11 tools):** `create_task`, `list_tasks`, `update_task`, `complete_task`, `search_tasks`, `save_memory`, `retrieve_memory`, `create_reminder`, `list_reminders`, `get_user_preferences`, `request_user_approval`.
- **Official MCP Layer (`mcp==2.3.0`):** `MCPClientManager` (`stdio_client` + `ClientSession`) + isolated `gmail_server.py` (6 tools) and `calendar_server.py` (8 tools).
- **Google OAuth 2.0:** Authorization Code + PKCE (`S256`), one-time CSRF `state`, Fernet token encryption at rest, automatic token refresh, revocation detection, and disconnect.
- **Human-in-the-Loop Approvals:** Reusable `PENDING -> APPROVED -> EXECUTED` / `REJECTED` / `EXPIRED` / `FAILED` workflow with interactive React Approval Cards (`Approve`, `Approve and Send`, `Edit Draft`, `Reject`).
- **React Frontend:** Chat interface, Tasks Dashboard, Memory Dashboard, Integrations Dashboard, and Settings/Profile Switcher.

---

## Partially Implemented / Development Foundations

- **LifeDesk Multi-User Auth:** Signed HMAC session tokens and full `user_id` isolation across all tables and endpoints are implemented; password/SSO verification and production auth gating (`ALLOW_DEMO_USER_FALLBACK=false`) remain for production hardening.
- **Live Google OAuth Verification:** OAuth flow and Gmail/Calendar MCP adapters are implemented and unit-tested with mocked Google APIs + real MCP STDIO discovery; live end-to-end verification against a real Google account depends on configuring `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `TOKEN_ENCRYPTION_KEY` in `backend/.env`.
- **Browser Automation & Web Search:** Typed policy/interface contracts (`WebSearchProvider`, `BrowserAutomationService`, `BrowserSecurityPolicy`, `validate_navigation_url`) are implemented in `backend/app/integrations/future_integrations.py`, without live execution yet.

---

## Planned Integrations & Production Tasks

1. **Google Drive MCP Server:** Search and summarize user Drive files with least-privilege `drive.readonly`.
2. **Web Search MCP Server:** Cited read-only search integration.
3. **Isolated Playwright Browser Automation MCP:** Ephemeral browser contexts restricted to allowlisted domains with approval gates.
4. **Notion & Slack MCP Servers:** OAuth-authorized workspace sync and approval-gated messaging.
5. **Production Infrastructure:** PostgreSQL + Alembic migrations, Redis rate limiting, KMS/MultiFernet key rotation, and Google OAuth CASA verification.
