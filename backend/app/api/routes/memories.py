"""REST endpoints for persistent user-scoped long-term memories."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import User
from app.database.repositories import MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryListResponse, MemoryOut, MemoryUpdate
from app.security.auth import get_current_user

router = APIRouter(prefix="/memories", tags=["Memories"])


@router.get("", response_model=MemoryListResponse)
def list_memories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryListResponse:
    """Return all stored long-term memories for the authenticated user."""
    repo = MemoryRepository(db, user_id=current_user.id)
    memories = repo.list_all()
    return MemoryListResponse(
        memories=[MemoryOut.model_validate(m) for m in memories],
        count=len(memories),
    )


@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def create_or_update_memory(
    payload: MemoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryOut:
    """Save a memory entry, updating existing entries with the same normalized key."""
    repo = MemoryRepository(db, user_id=current_user.id)
    memory, _action = repo.upsert(key=payload.key, value=payload.value)
    return MemoryOut.model_validate(memory)


@router.patch("/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: int,
    payload: MemoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryOut:
    """Update a user-owned memory entry's key or value by ID."""
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide key or value to update.",
        )

    repo = MemoryRepository(db, user_id=current_user.id)
    try:
        memory = repo.update_by_id(memory_id, key=payload.key, value=payload.value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} was not found.",
        )
    return MemoryOut.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a user-owned memory by ID."""
    repo = MemoryRepository(db, user_id=current_user.id)
    deleted = repo.delete(memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
