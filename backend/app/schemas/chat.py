"""Pydantic schemas for chat, conversations, tool audit records, and health checks."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolExecutionRecord(BaseModel):
    """Audit record returned to the frontend for a backend-executed tool."""

    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    success: bool
    result: dict[str, Any]


class ChatRequest(BaseModel):
    """HTTP request payload for POST /api/chat."""

    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: int | None = Field(default=None, ge=1)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")
        return cleaned


class ChatResponse(BaseModel):
    """HTTP response payload for POST /api/chat."""

    conversation_id: int
    reply: str
    provider: str
    model: str
    iterations_used: int
    tool_calls: list[ToolExecutionRecord] = Field(default_factory=list)


class ConversationOut(BaseModel):
    """Serialized conversation summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Response payload for GET /api/conversations."""

    conversations: list[ConversationOut]
    count: int


class MessageOut(BaseModel):
    """Serialized persisted message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    tool_calls: list[ToolExecutionRecord] = Field(default_factory=list)
    created_at: datetime


class MessageListResponse(BaseModel):
    """Response payload for GET /api/conversations/{conversation_id}/messages."""

    conversation: ConversationOut
    messages: list[MessageOut]


class ProviderStatus(BaseModel):
    """Safe LLM provider status without exposing API credentials."""

    provider: str
    model: str
    base_url: str
    configured: bool
    status_message: str


class HealthResponse(BaseModel):
    """Response payload for GET /api/health."""

    status: str
    database: str
    llm: ProviderStatus
