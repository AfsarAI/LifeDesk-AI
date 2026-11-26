# LifeDesk AI — System Architecture

LifeDesk AI is designed as a modular, multi-user Personal AI Chief of Staff combining **native application tools** with **Model Context Protocol (MCP)** integrations and **human-in-the-loop approvals**.

---

## 1. High-Level System Diagram

```mermaid
flowchart TB
    subgraph Frontend["React + TypeScript + Vite (localhost:5173)"]
        UI_Chat["ChatPage + ApprovalCard"]
        UI_Tasks["TasksPage"]
        UI_Memory["MemoryPage"]
        UI_Integ["IntegrationsPage"]
        UI_Settings["SettingsPage"]
        APIClient["services/apiClient.ts"]
        UI_Chat --> APIClient
        UI_Tasks --> APIClient
        UI_Memory --> APIClient
        UI_Integ --> APIClient
        UI_Settings --> APIClient
    end

    subgraph Backend["FastAPI Backend (127.0.0.1:8000)"]
        Auth["security/auth.py (get_current_user)"]
        Routes["API Routes (/api/*)"]
        Agent["agent/agent.py (LifeDeskAgent)"]
        LLM["agent/llm_provider.py (Groq / OpenRouter)"]
        Unified["agent/unified_tools.py (UnifiedToolExecutor)"]
        Native["agent/tool_registry.py (11 Native Tools)"]
        ApprovalSvc["approvals/service.py (ApprovalService)"]
        OAuth["integrations/google_oauth.py (PKCE + Fernet)"]
        MCPClient["mcp_client/client.py (STDIO ClientSession)"]
        DB[("SQLite + SQLAlchemy")]

        Routes --> Auth
        Routes --> Agent
        Routes --> OAuth
        Routes --> ApprovalSvc
        Agent --> LLM
        Agent --> Unified
        Unified --> Native
        Unified --> ApprovalSvc
        Unified --> MCPClient
        Unified --> OAuth
        ApprovalSvc --> OAuth
        ApprovalSvc --> MCPClient
        Native --> DB
        OAuth --> DB
        ApprovalSvc --> DB
    end

    subgraph MCP["Isolated Per-User MCP Subprocesses"]
        GmailMCP["mcp_servers/gmail_server.py"]
        CalMCP["mcp_servers/calendar_server.py"]
        MCPClient -->|"STDIO + short-lived access token"| GmailMCP
        MCPClient -->|"STDIO + short-lived access token"| CalMCP
    end

    GmailMCP -->|"HTTPS"| GoogleGmail["Google Gmail API v1"]
    CalMCP -->|"HTTPS"| GoogleCal["Google Calendar API v3"]
    APIClient -->|"REST JSON + Bearer Token"| Routes
```

---

## 2. Frontend Architecture

- **`src/services/apiClient.ts`**: Single HTTP gateway attaching `Authorization: Bearer <token>` when a user session token is active, never storing Google credentials.
- **`src/hooks/useLifeDeskData.ts`**: Synchronizes tasks, memories, conversations, integrations, approvals, user profiles, and backend health.
- **Pages**:
  - `ChatPage.tsx`: Displays conversation history, real tool-execution status (`ToolCallList.tsx`), and interactive approval cards (`ApprovalCard.tsx`).
  - `TasksPage.tsx` & `MemoryPage.tsx`: Full CRUD backed by SQLite.
  - `IntegrationsPage.tsx`: Displays Gmail & Google Calendar connection state, OAuth callbacks, and planned Coming Soon integrations.
  - `SettingsPage.tsx`: Displays LLM provider status, timezone settings, and local user profile switching.

---

## 3. Backend Architecture & Layer Separation

1. **API Layer (`backend/app/api/routes/`)**: Validates HTTP payloads with Pydantic, resolves the authenticated user via `Depends(get_current_user)`, applies sliding-window rate limiting on sensitive endpoints, and maps domain exceptions to HTTP status codes.
2. **Agent Orchestration (`backend/app/agent/agent.py`)**: Runs a bounded loop (`max_tool_iterations = 5`), preserves conversation history in SQLite, injects timezone context, defends against prompt injection from external data, and passes unified tool schemas to the LLM.
3. **LLM Provider (`backend/app/agent/llm_provider.py`)**: Uses `openai.OpenAI` with provider-specific `base_url` (`https://api.groq.com/openai/v1` or `https://openrouter.ai/api/v1`) without hardcoding secrets or silently switching to paid models.
4. **Unified Tool Abstraction (`backend/app/agent/unified_tools.py`)**: Presents native and MCP tools identically to the LLM while preserving `source`, `provider`, `required_scopes`, `requires_approval`, and Pydantic argument validation.
5. **MCP Layer (`backend/app/mcp_client/` + `backend/app/mcp_servers/`)**: Uses `mcp==2.3.0` (`MCPServer`, `stdio_client`, `ClientSession`) to isolate Google API calls in dedicated subprocesses per user invocation.
6. **Database Layer (`backend/app/database/`)**: SQLAlchemy 2.x ORM models and user-scoped repositories with non-destructive SQLite schema migrations on startup.

---

## 4. Google OAuth & Approval Execution Sequence

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant API as FastAPI Backend
    participant G as Google OAuth / APIs
    participant MCP as MCP Server (STDIO)

    U->>API: GET /api/integrations/google/connect?service=both
    API->>API: Store one-time state + PKCE code_verifier in oauth_states
    API-->>U: Return Google consent URL
    U->>G: User approves Gmail & Calendar scopes
    G-->>API: GET /api/integrations/google/callback?code=...&state=...
    API->>API: Validate & consume state, exchange code + verifier
    API->>API: Encrypt access & refresh tokens with Fernet (TOKEN_ENCRYPTION_KEY)
    API-->>U: Redirect to /?page=integrations&oauth=connected

    U->>API: POST /api/chat ("Add Rahul's meeting to calendar")
    API->>MCP: gmail_search_emails & calendar_find_conflicts (access token in isolated env)
    MCP-->>API: Untrusted email data + conflict check
    API->>API: Stage PENDING Approval for calendar_create_event
    API-->>U: Chat reply + ApprovalCard (Approve / Reject)

    U->>API: POST /api/approvals/{id}/approve
    API->>API: Atomic PENDING -> APPROVED transition (user_id check)
    API->>MCP: calendar_create_event (exact stored payload)
    MCP->>G: Insert event on primary calendar
    G-->>MCP: Event created
    MCP-->>API: Success result
    API-->>U: Status EXECUTED
```

---

## 5. Database Schema Design

All user-owned tables include `user_id` with foreign-key constraints:
- `users`: `id`, `name`, `email`, `timezone`, `created_at`
- `tasks`: `id`, `user_id`, `title`, `description`, `due_date`, `status`, `created_at`, `updated_at`
- `reminders`: `id`, `user_id`, `task_id`, `title`, `remind_at`, `status`, `created_at`
- `conversations`: `id`, `user_id`, `title`, `created_at`, `updated_at`
- `messages`: `id`, `conversation_id`, `role`, `content`, `tool_metadata`, `created_at`
- `memories`: `id`, `user_id`, `key`, `value`, `created_at`, `updated_at` (`UNIQUE(user_id, key)`)
- `integrations`: `id`, `user_id`, `provider`, `account_email`, `status`, `granted_scopes`, `last_connected_at` (`UNIQUE(user_id, provider)`)
- `integration_credentials`: `id`, `integration_id`, `encrypted_access_token`, `encrypted_refresh_token`, `token_expiry`, `encryption_version`
- `oauth_states`: `id`, `state`, `user_id`, `service`, `requested_scopes`, `code_verifier`, `expires_at`
- `approvals`: `id`, `user_id`, `conversation_id`, `provider`, `tool_name`, `action_type`, `action_payload`, `summary`, `status`, `expires_at`, `approved_at`, `executed_at`, `execution_result`
- `tool_executions`: `id`, `user_id`, `conversation_id`, `tool_name`, `tool_source`, `status`, `duration_ms`, `safe_error_summary`, `created_at`
