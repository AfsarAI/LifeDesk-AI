"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

# Load variables from backend/.env or root .env without overriding exported env vars.
load_dotenv(override=False)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Settings(BaseModel):
    """Validated runtime settings for LifeDesk AI."""

    llm_provider: Literal["groq", "openrouter"] = Field(default="groq")
    groq_api_key: str | None = Field(default=None)
    groq_model: str = Field(default="openai/gpt-oss-20b", min_length=1)
    openrouter_api_key: str | None = Field(default=None)
    openrouter_model: str = Field(default="openrouter/free", min_length=1)
    database_url: str = Field(default="sqlite:///./lifedesk.db", min_length=1)
    max_tool_iterations: int = Field(default=5, ge=1, le=10)
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )


def _clean_secret(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    cleaned = raw_value.strip()
    placeholders = {
        "your-groq-api-key-here",
        "your-openrouter-api-key-here",
        "your-api-key-here",
    }
    if not cleaned or cleaned in placeholders:
        return None
    return cleaned


@lru_cache
def get_settings() -> Settings:
    """Load and cache application settings from environment variables."""
    provider_raw = os.getenv("LLM_PROVIDER", "groq").strip().lower() or "groq"
    max_iter_raw = os.getenv("MAX_TOOL_ITERATIONS", "5").strip() or "5"
    cors_raw = os.getenv("CORS_ORIGINS", "").strip()

    try:
        max_iterations = int(max_iter_raw)
    except ValueError as exc:
        raise RuntimeError("MAX_TOOL_ITERATIONS must be an integer.") from exc

    cors_origins = (
        [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
        if cors_raw
        else ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

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
            cors_origins=cors_origins,
        )
    except ValidationError as exc:
        raise RuntimeError(f"Invalid configuration: {exc}") from exc
