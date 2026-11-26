"""Long-term key-value memory tools backed by SQLite via user-scoped MemoryRepository."""

from typing import Any

from sqlalchemy.orm import Session

from app.database.repositories import MemoryRepository
from app.schemas.memory import MemoryOut, RetrieveMemoryArgs, SaveMemoryArgs


def _serialize_memory(memory: Any) -> dict[str, Any]:
    return MemoryOut.model_validate(memory).model_dump(mode="json")


def save_memory_tool(db: Session, args: SaveMemoryArgs, *, user_id: int = 1) -> dict[str, Any]:
    """Save or update a persistent user preference/memory without duplicates."""
    repo = MemoryRepository(db, user_id=user_id)
    memory, action = repo.upsert(key=args.key, value=args.value)
    return {
        "status": action,
        "memory": _serialize_memory(memory),
    }


def retrieve_memory_tool(
    db: Session,
    args: RetrieveMemoryArgs,
    *,
    user_id: int = 1,
) -> dict[str, Any]:
    """Retrieve a specific memory by key, or list all stored memories if key is omitted."""
    repo = MemoryRepository(db, user_id=user_id)
    if args.key:
        memory = repo.get_by_key(args.key)
        if memory is None:
            return {
                "status": "not_found",
                "key": args.key,
                "memories": [],
            }
        return {
            "status": "ok",
            "memory": _serialize_memory(memory),
            "memories": [_serialize_memory(memory)],
        }

    memories = repo.list_all()
    return {
        "status": "ok",
        "count": len(memories),
        "memories": [_serialize_memory(m) for m in memories],
    }
