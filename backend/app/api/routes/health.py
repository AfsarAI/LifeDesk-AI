"""Health and safe LLM provider status endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.llm_provider import LLMConfigurationError, LLMProvider
from app.config import Settings, get_settings
from app.database.database import get_db
from app.schemas.chat import HealthResponse, ProviderStatus

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Verify database connectivity and expose non-secret LLM provider settings."""
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        provider_status = LLMProvider(settings).get_status()
    except LLMConfigurationError as exc:
        provider_status = ProviderStatus(
            provider=settings.llm_provider,
            model="",
            base_url="",
            configured=False,
            status_message=str(exc),
        )

    overall = "ok" if db_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status, llm=provider_status)
