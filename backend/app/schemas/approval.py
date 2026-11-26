"""Pydantic schemas for the human-in-the-loop approval lifecycle."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApprovalOut(BaseModel):
    """Serialized approval request exposed to the frontend (bound to user_id)."""

    id: int
    user_id: int
    conversation_id: int | None = None
    provider: str
    tool_name: str
    action_type: str
    action_payload: dict[str, Any]
    summary: str
    status: str  # PENDING | APPROVED | EXECUTED | REJECTED | EXPIRED | FAILED | CANCELLED
    expires_at: datetime
    created_at: datetime
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    execution_result: dict[str, Any] | None = None


class ApprovalListResponse(BaseModel):
    """Response payload for GET /api/approvals."""

    approvals: list[ApprovalOut]
    pending_count: int


class ApprovalDecisionResponse(BaseModel):
    """Response payload for approve/reject actions."""

    approval: ApprovalOut
    message: str


class RequestUserApprovalArgs(BaseModel):
    """Tool schema allowing the agent to stage an explicit approval request."""

    model_config = ConfigDict(extra="forbid")

    action_type: str = Field(..., min_length=1, max_length=80)
    provider: str = Field(default="internal", min_length=1, max_length=50)
    tool_name: str = Field(..., min_length=1, max_length=80)
    summary: str = Field(..., min_length=1, max_length=500)
    action_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider", mode="before")
    @classmethod
    def default_provider_if_none(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "internal"
        return value
