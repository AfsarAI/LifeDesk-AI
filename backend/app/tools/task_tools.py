"""Task management tools backed by SQLite via user-scoped TaskRepository."""

from typing import Any

from sqlalchemy.orm import Session

from app.database.repositories import TaskRepository
from app.schemas.task import (
    CompleteTaskArgs,
    CreateTaskArgs,
    ListTasksArgs,
    SearchTasksArgs,
    TaskOut,
    UpdateTaskArgs,
)


def _serialize_task(task: Any) -> dict[str, Any]:
    return TaskOut.model_validate(task).model_dump(mode="json")


def create_task_tool(db: Session, args: CreateTaskArgs, *, user_id: int = 1) -> dict[str, Any]:
    """Create and persist a new task in SQLite for the authenticated user."""
    repo = TaskRepository(db, user_id=user_id)
    task = repo.create(
        title=args.title,
        due_date=args.due_date,
        description=args.description,
    )
    return {
        "status": "created",
        "task": _serialize_task(task),
    }


def list_tasks_tool(db: Session, args: ListTasksArgs, *, user_id: int = 1) -> dict[str, Any]:
    """List tasks from SQLite for the authenticated user, optionally filtered by status."""
    repo = TaskRepository(db, user_id=user_id)
    tasks = repo.list_all(status=args.status)
    return {
        "status": "ok",
        "count": len(tasks),
        "tasks": [_serialize_task(task) for task in tasks],
    }


def update_task_tool(db: Session, args: UpdateTaskArgs, *, user_id: int = 1) -> dict[str, Any]:
    """Update an existing user-owned task's title, due_date, or description."""
    if args.title is None and args.due_date is None and args.description is None:
        return {
            "status": "error",
            "error": "Provide at least one field to update (title, due_date, or description).",
        }

    repo = TaskRepository(db, user_id=user_id)
    task = repo.update(
        args.task_id,
        title=args.title,
        description=args.description,
        due_date=args.due_date,
    )
    if task is None:
        return {
            "status": "error",
            "error": f"Task with id {args.task_id} was not found.",
        }

    return {
        "status": "updated",
        "task": _serialize_task(task),
    }


def complete_task_tool(db: Session, args: CompleteTaskArgs, *, user_id: int = 1) -> dict[str, Any]:
    """Mark an existing user-owned task as completed."""
    repo = TaskRepository(db, user_id=user_id)
    task = repo.complete(args.task_id)
    if task is None:
        return {
            "status": "error",
            "error": f"Task with id {args.task_id} was not found.",
        }

    return {
        "status": "completed",
        "task": _serialize_task(task),
    }


def search_tasks_tool(db: Session, args: SearchTasksArgs, *, user_id: int = 1) -> dict[str, Any]:
    """Search user-owned tasks by title or description using safe parameterized queries."""
    repo = TaskRepository(db, user_id=user_id)
    tasks = repo.search(args.query)
    return {
        "status": "ok",
        "query": args.query,
        "count": len(tasks),
        "tasks": [_serialize_task(task) for task in tasks],
    }
