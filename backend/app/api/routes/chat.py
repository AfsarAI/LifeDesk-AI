"""Chat endpoint connecting HTTP requests to LifeDeskAgent."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.agent import AgentExecutionError, ConversationNotFoundError, LifeDeskAgent
from app.agent.llm_provider import LLMConfigurationError, LLMProviderError
from app.config import Settings, get_settings
from app.database.database import get_db
from app.database.models import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.security.auth import get_current_user, sensitive_rate_limiter

router = APIRouter(tags=["Chat"])


def get_agent(settings: Settings = Depends(get_settings)) -> LifeDeskAgent:
    """Construct a LifeDeskAgent instance from runtime settings."""
    return LifeDeskAgent(settings=settings)


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: LifeDeskAgent = Depends(get_agent),
) -> ChatResponse:
    """Process a user message through the unified native + MCP agent."""
    sensitive_rate_limiter.check(f"chat:{current_user.id}")
    try:
        return agent.run(
            db,
            user_message=payload.message,
            conversation_id=payload.conversation_id,
            user=current_user,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
