"""Pydantic schemas for LifeDesk local user authentication and profile switching."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserOut(BaseModel):
    """Safe user profile (never includes OAuth credentials)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    email: str | None = None
    timezone: str
    created_at: datetime


class UserRegisterRequest(BaseModel):
    """Create a LifeDesk user account for multi-user isolation or demo switching."""

    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=255)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)

    @field_validator("name", "email", "timezone")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned


class UserLoginRequest(BaseModel):
    """Sign in by user ID or email to receive a signed LifeDesk session token."""

    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, min_length=3, max_length=255)


class AuthSessionResponse(BaseModel):
    """Session token and authenticated user profile."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserListResponse(BaseModel):
    """List of local LifeDesk user profiles."""

    users: list[UserOut]
