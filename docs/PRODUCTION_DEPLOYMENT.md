# Production Deployment Guide

This guide outlines what is needed to take LifeDesk AI from local MVP to a multi-user production environment.

---

## 1. Recommended Production Topology

- **HTTPS Termination:** Reverse proxy (Cloudflare / Nginx / AWS ALB / Caddy) enforcing TLS 1.2+ with HSTS.
- **Frontend Hosting:** Build static assets (`cd frontend && npm run build`) and serve `dist/` via CDN/Vercel/Cloudflare Pages with `VITE_API_BASE_URL=https://api.yourdomain.com/api`.
- **Backend Hosting:** Containerized FastAPI (`uvicorn` behind Gunicorn or Cloud Run / ECS / Fly.io) running with `ALLOW_DEMO_USER_FALLBACK=false` and `DEMO_MODE=false`.
- **Database Migration (SQLite → PostgreSQL):**
  - Replace `DATABASE_URL=sqlite:///./lifedesk.db` with `postgresql+psycopg://...` on managed PostgreSQL (RDS / Supabase / Cloud SQL).
  - Introduce **Alembic** migrations for versioned schema evolution and automated encrypted daily backups.

---

## 2. Secret & Key Management

Store all secrets in a dedicated secret manager (AWS Secrets Manager, GCP Secret Manager, or Vault), never in Git or Docker images:
- `APP_SECRET_KEY` (32+ random bytes for signing LifeDesk session tokens)
- `TOKEN_ENCRYPTION_KEY` (Fernet key; plan KMS envelope encryption / `MultiFernet` rotation for enterprise scale)
- `GROQ_API_KEY` / `OPENROUTER_API_KEY`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`

---

## 3. Google OAuth Production Setup

1. Set `GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/integrations/google/callback` and `FRONTEND_URL=https://app.yourdomain.com`.
2. Register those exact production URLs in Google Cloud Console.
3. Publish the OAuth consent screen from **Testing** to **In Production** and complete:
   - **Sensitive Scope Verification** for Google Calendar scopes.
   - **Restricted Scope Verification + CASA Security Assessment** for Gmail scopes (`gmail.readonly`, `gmail.compose`, `gmail.send`).

---

## 4. Scaling, Observability & Background Work

- **Auth Hardening:** Add password/passkey or OIDC login in `/api/auth/*` before opening registration publicly.
- **Rate Limiting:** Replace in-memory `InMemoryRateLimiter` with Redis-backed limits across multiple backend replicas.
- **MCP Scaling:** For higher concurrency, replace per-call STDIO subprocess spawning with pooled per-user worker processes or authenticated Streamable HTTP MCP microservices inside a private VPC, keeping strict per-user credential boundaries.
- **Logging & Monitoring:** Forward structured logs (`tool_executions`, HTTP latency, OAuth refresh failure rates) to OpenTelemetry/Datadog/CloudWatch—continuing to exclude tokens and email bodies.
- **Background Jobs:** Use a task queue (Celery/ARQ/Cloud Tasks) for scheduled daily briefings or proactive reminder notifications.
