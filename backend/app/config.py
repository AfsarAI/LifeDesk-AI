"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache
import secrets
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

# Load variables from backend/.env or root .env without overriding exported env vars.
load_dotenv(override=False)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Ephemeral per-process fallback secret for local development only when APP_SECRET_KEY is unset.
_DEV_FALLBACK_APP_SECRET = secrets.token_urlsafe(32)


class Settings(BaseModel):
    """Validated runtime settings for LifeDesk AI."""

    llm_provider: Literal["groq", "openrouter"] = Field(default="groq")
    groq_api_key: str | None = Field(default=None)
    groq_model: str = Field(default="openai/gpt-oss-20b", min_length=1)
    openrouter_api_key: str | None = Field(default=None)
    openrouter_model: str = Field(default="openrouter/free", min_length=1)

    database_url: str = Field(default="sqlite:///./lifedesk.db", min_length=1)
    max_tool_iterations: int = Field(default=5, ge=1, le=10)
    frontend_url: str = Field(default="http://localhost:5173", min_length=1)
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    # Google OAuth 2.0 & Token Security
    google_client_id: str | None = Field(default=None)
    google_client_secret: str | None = Field(default=None)
    google_redirect_uri: str = Field(
        default="http://localhost:8000/api/integrations/google/callback",
        min_length=1,
    )
    token_encryption_key: str | None = Field(default=None)

    # LifeDesk Session Authentication & Development Flags
    app_secret_key: str = Field(default_factory=lambda: _DEV_FALLBACK_APP_SECRET, min_length=16)
    allow_demo_user_fallback: bool = Field(default=True)
    demo_mode: bool = Field(default=False)
    default_timezone: str = Field(default="UTC", min_length=1)


def _clean_secret(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    cleaned = raw_value.strip()
    placeholders = {
        "your-groq-api-key-here",
        "your-openrouter-api-key-here",
        "your-api-key-here",
        "your-google-client-id",
        "your-google-client-secret",
        "your-fernet-token-encryption-key",
    }
    if not cleaned or cleaned in placeholders:
        return None
    return cleaned


def _parse_bool(raw_value: str | None, default: bool) -> bool:
    if raw_value is None or not raw_value.strip():
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    """Load and cache application settings from environment variables."""
    provider_raw = os.getenv("LLM_PROVIDER", "groq").strip().lower() or "groq"
    max_iter_raw = os.getenv("MAX_TOOL_ITERATIONS", "5").strip() or "5"
    frontend_url = (
        os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")
        or "http://localhost:5173"
    )
    cors_raw = os.getenv("CORS_ORIGINS", "").strip()

    try:
        max_iterations = int(max_iter_raw)
    except ValueError as exc:
        raise RuntimeError("MAX_TOOL_ITERATIONS must be an integer.") from exc

    cors_origins = (
        [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
        if cors_raw
        else list({frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"})
    )

    app_secret = _clean_secret(os.getenv("APP_SECRET_KEY")) or _DEV_FALLBACK_APP_SECRET

    try:
        return Settings(
            llm_provider=provider_raw,  # type: ignore[arg-type]
            groq_api_key=_clean_secret(os.getenv("GROQ_API_KEY")),
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
            or "openai/gpt-oss-20b",
            openrouter_api_key=_clean_secret(os.getenv("OPENROUTER_API_KEY")),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()
            or "openrouter/free",
            database_url=os.getenv("DATABASE_URL", "sqlite:///./lifedesk.db").strip()
            or "sqlite:///./lifedesk.db",
            max_tool_iterations=max_iterations,
            frontend_url=frontend_url,
            cors_origins=cors_origins,
            google_client_id=_clean_secret(os.getenv("GOOGLE_CLIENT_ID")),
            google_client_secret=_clean_secret(os.getenv("GOOGLE_CLIENT_SECRET")),
            google_redirect_uri=os.getenv(
                "GOOGLE_REDIRECT_URI",
                "http://localhost:8000/api/integrations/google/callback",
            ).strip()
            or "http://localhost:8000/api/integrations/google/callback",
            token_encryption_key=_clean_secret(os.getenv("TOKEN_ENCRYPTION_KEY")),
            app_secret_key=app_secret,
            allow_demo_user_fallback=_parse_bool(os.getenv("ALLOW_DEMO_USER_FALLBACK"), True),
            demo_mode=_parse_bool(os.getenv("DEMO_MODE"), False),
            default_timezone=os.getenv("USER_TIMEZONE", "UTC").strip() or "UTC",
        )
    except ValidationError as exc:
        raise RuntimeError(f"Invalid configuration: {exc}") from exc
