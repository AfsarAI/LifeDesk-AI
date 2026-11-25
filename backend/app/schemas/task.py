"""Pydantic schemas for tasks and task tool arguments."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class CreateTaskArgs(BaseModel):
    """Validated tool arguments for `create_task`."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    due_date: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task title cannot be empty.")
        return cleaned

    @field_validator("due_date", "description")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ListTasksArgs(BaseModel):
    """Validated tool arguments for `list_tasks`."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["pending", "completed"] | None = Field(default=None)


class UpdateTaskArgs(BaseModel):
    """Validated tool arguments for `update_task`."""

    model_config = ConfigDict(extra="forbid")

    task_id: int = Field(..., ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_date: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task title cannot be blank.")
        return cleaned

    @field_validator("due_date", "description")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class CompleteTaskArgs(BaseModel):
    """Validated tool arguments for `complete_task`."""

    model_config = ConfigDict(extra="forbid")

    task_id: int = Field(..., ge=1)


class SearchTasksArgs(BaseModel):
    """Validated tool arguments for `search_tasks`."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=200)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Search query cannot be empty.")
        return cleaned


class TaskCreate(CreateTaskArgs):
    """HTTP request payload for POST /api/tasks."""


class TaskUpdate(BaseModel):
    """HTTP request payload for PATCH /api/tasks/{task_id}."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: str | None = Field(default=None, max_length=100)
    status: Literal["pending", "completed"] | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task title cannot be blank.")
        return cleaned


class TaskOut(BaseModel):
    """Serialized task response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    due_date: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Response payload for GET /api/tasks."""

    tasks: list[TaskOut]
    count: int
    pending_count: int
    completed_count: int
