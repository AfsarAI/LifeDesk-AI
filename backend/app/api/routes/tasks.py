"""REST endpoints for persistent tasks."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.repositories import TaskRepository
from app.schemas.task import TaskCreate, TaskListResponse, TaskOut, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(
    task_status: Literal["pending", "completed"] | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    """List tasks with optional status/search filtering plus summary counts."""
    repo = TaskRepository(db)
    all_tasks = repo.list_all()
    filtered = repo.list_all(status=task_status, query=q) if (task_status or q) else all_tasks
    pending_count = sum(1 for t in all_tasks if t.status == "pending")
    completed_count = sum(1 for t in all_tasks if t.status == "completed")
    return TaskListResponse(
        tasks=[TaskOut.model_validate(t) for t in filtered],
        count=len(filtered),
        pending_count=pending_count,
        completed_count=completed_count,
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> TaskOut:
    """Create a task directly from the Tasks dashboard."""
    repo = TaskRepository(db)
    task = repo.create(
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
    )
    return TaskOut.model_validate(task)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
) -> TaskOut:
    """Update task fields or toggle completion status."""
    fields = payload.model_fields_set
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one field to update.",
        )

    repo = TaskRepository(db)
    task = repo.update(
        task_id,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        status=payload.status,
        clear_description=("description" in fields and payload.description is None),
        clear_due_date=("due_date" in fields and payload.due_date is None),
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} was not found.",
        )
    return TaskOut.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a task by ID."""
    repo = TaskRepository(db)
    deleted = repo.delete(task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
