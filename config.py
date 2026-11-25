"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

# Load variables from a local .env file if present without overriding shell exports.
load_dotenv(override=False)


class Settings(BaseModel):
    """Validated runtime settings for MiniTask Agent."""

    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-4-hydrogen", min_length=1)
    max_tool_iterations: int = Field(default=5, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    """Load and cache application settings from the environment."""
    raw_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_api_key = raw_key if raw_key and raw_key != "your-gemini-api-key-here" else None

    raw_model = os.getenv("GEMINI_MODEL", "gemini-4-hydrogen").strip() or "gemini-4-hydrogen"
    raw_max_iterations = os.getenv("MAX_TOOL_ITERATIONS", "5").strip() or "5"

    try:
        max_iterations = int(raw_max_iterations)
    except ValueError as exc:
        raise RuntimeError("MAX_TOOL_ITERATIONS must be an integer.") from exc

    try:
        return Settings(
            gemini_api_key=gemini_api_key,
            gemini_model=raw_model,
            max_tool_iterations=max_iterations,
        )
    except ValidationError as exc:
        raise RuntimeError(f"Invalid application configuration: {exc}") from exc
