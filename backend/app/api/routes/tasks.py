"""REST endpoints for persistent user-scoped tasks."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import User
from app.database.repositories import TaskRepository
from app.schemas.task import TaskCreate, TaskListResponse, TaskOut, TaskUpdate
from app.security.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(
    task_status: Literal["pending", "completed"] | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    """List tasks belonging to the authenticated user."""
    repo = TaskRepository(db, user_id=current_user.id)
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
def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    """Create a task directly from the Tasks dashboard."""
    repo = TaskRepository(db, user_id=current_user.id)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    """Update task fields or toggle completion status for the authenticated user."""
    fields = payload.model_fields_set
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one field to update.",
        )

    repo = TaskRepository(db, user_id=current_user.id)
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
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a user-owned task by ID."""
    repo = TaskRepository(db, user_id=current_user.id)
    deleted = repo.delete(task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
