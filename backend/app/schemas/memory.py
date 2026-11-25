"""Pydantic schemas for persistent memory and memory tool arguments."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SaveMemoryArgs(BaseModel):
    """Validated tool arguments for `save_memory`."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=150)
    value: str = Field(..., min_length=1, max_length=2000)

    @field_validator("key", "value")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Memory key and value cannot be empty.")
        return cleaned


class RetrieveMemoryArgs(BaseModel):
    """Validated tool arguments for `retrieve_memory`."""

    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(default=None, max_length=150)

    @field_validator("key")
    @classmethod
    def clean_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class MemoryCreate(SaveMemoryArgs):
    """HTTP request payload for POST /api/memories."""


class MemoryUpdate(BaseModel):
    """HTTP request payload for PATCH /api/memories/{memory_id}."""

    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(default=None, min_length=1, max_length=150)
    value: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("key", "value")
    @classmethod
    def validate_non_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Memory field cannot be blank.")
        return cleaned


class MemoryOut(BaseModel):
    """Serialized memory entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str
    created_at: datetime
    updated_at: datetime


class MemoryListResponse(BaseModel):
    """Response payload for GET /api/memories."""

    memories: list[MemoryOut]
    count: int
