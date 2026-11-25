"""FastAPI entrypoint and HTTP routes for MiniTask Agent."""

from fastapi import Depends, FastAPI, HTTPException, status

from agent import AgentConfigurationError, AgentExecutionError, MiniTaskAgent
from config import Settings, get_settings
from schemas import ChatRequest, ChatResponse, TaskListResponse
from tools import list_tasks

app = FastAPI(
    title="LifeDesk AI — MiniTask Agent",
    description="Day 1 FastAPI backend demonstrating safe Gemini function calling.",
    version="0.1.0",
)


def get_agent(settings: Settings = Depends(get_settings)) -> MiniTaskAgent:
    """Build a MiniTaskAgent dependency configured from runtime settings."""
    return MiniTaskAgent(settings=settings)


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "ok", "service": "minitask-agent"}


@app.get("/tasks", response_model=TaskListResponse, tags=["Tasks"])
def get_tasks() -> TaskListResponse:
    """List all tasks currently stored in temporary in-memory storage."""
    tasks = list_tasks()
    return TaskListResponse(tasks=tasks, count=len(tasks))


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(
    payload: ChatRequest,
    agent: MiniTaskAgent = Depends(get_agent),
) -> ChatResponse:
    """Send a user message to Gemini, execute any validated tool calls, and return the reply."""
    try:
        return agent.run(payload.message)
    except AgentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
