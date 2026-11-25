"""FastAPI application entrypoint with CORS, DB initialization, and /api routes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, conversations, health, memories, tasks
from app.config import get_settings
from app.database.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize SQLite tables and local demo user on server startup."""
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title="LifeDesk AI Backend",
        description="Multi-tool AI Agent backend with Groq/OpenRouter switching and SQLite persistence.",
        version="0.2.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, prefix="/api")
    application.include_router(chat.router, prefix="/api")
    application.include_router(tasks.router, prefix="/api")
    application.include_router(memories.router, prefix="/api")
    application.include_router(conversations.router, prefix="/api")

    return application


app = create_app()
