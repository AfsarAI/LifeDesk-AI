"""Database repository layer separating SQLAlchemy queries from routes and tools."""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database.models import Conversation, Memory, Message, Task, utc_now


def normalize_memory_key(raw_key: str) -> str:
    """Normalize memory keys so equivalent casing/spacing maps to one key."""
    return "_".join(raw_key.strip().lower().split())


class TaskRepository:
    """CRUD and search operations for Task rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        title: str,
        description: str | None = None,
        due_date: str | None = None,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            due_date=due_date,
            status="pending",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def list_all(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
    ) -> list[Task]:
        stmt = self.db.query(Task)
        if status is not None:
            stmt = stmt.filter(Task.status == status)
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.filter(
                or_(
                    Task.title.ilike(pattern),
                    Task.description.ilike(pattern),
                )
            )
        return stmt.order_by(Task.id.asc()).all()

    def get_by_id(self, task_id: int) -> Task | None:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def update(
        self,
        task_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        status: str | None = None,
        clear_description: bool = False,
        clear_due_date: bool = False,
    ) -> Task | None:
        task = self.get_by_id(task_id)
        if task is None:
            return None

        if title is not None:
            task.title = title
        if clear_description:
            task.description = None
        elif description is not None:
            task.description = description
        if clear_due_date:
            task.due_date = None
        elif due_date is not None:
            task.due_date = due_date
        if status is not None:
            task.status = status
        task.updated_at = utc_now()

        self.db.commit()
        self.db.refresh(task)
        return task

    def complete(self, task_id: int) -> Task | None:
        return self.update(task_id, status="completed")

    def delete(self, task_id: int) -> bool:
        task = self.get_by_id(task_id)
        if task is None:
            return False
        self.db.delete(task)
        self.db.commit()
        return True

    def search(self, query: str) -> list[Task]:
        return self.list_all(query=query)


class MemoryRepository:
    """CRUD and deduplicating upsert operations for Memory rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Memory]:
        return self.db.query(Memory).order_by(Memory.updated_at.desc(), Memory.id.asc()).all()

    def get_by_id(self, memory_id: int) -> Memory | None:
        return self.db.query(Memory).filter(Memory.id == memory_id).first()

    def get_by_key(self, raw_key: str) -> Memory | None:
        normalized = normalize_memory_key(raw_key)
        return (
            self.db.query(Memory)
            .filter(func.lower(Memory.key) == normalized)
            .first()
        )

    def upsert(self, *, key: str, value: str) -> tuple[Memory, str]:
        normalized_key = normalize_memory_key(key)
        existing = self.get_by_key(normalized_key)
        if existing is not None:
            existing.value = value
            existing.updated_at = utc_now()
            self.db.commit()
            self.db.refresh(existing)
            return existing, "updated"

        memory = Memory(key=normalized_key, value=value)
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory, "created"

    def update_by_id(
        self,
        memory_id: int,
        *,
        key: str | None = None,
        value: str | None = None,
    ) -> Memory | None:
        memory = self.get_by_id(memory_id)
        if memory is None:
            return None

        if key is not None:
            normalized_key = normalize_memory_key(key)
            conflict = (
                self.db.query(Memory)
                .filter(func.lower(Memory.key) == normalized_key, Memory.id != memory_id)
                .first()
            )
            if conflict is not None:
                raise ValueError(f"Memory key '{normalized_key}' already exists.")
            memory.key = normalized_key

        if value is not None:
            memory.value = value

        memory.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def delete(self, memory_id: int) -> bool:
        memory = self.get_by_id(memory_id)
        if memory is None:
            return False
        self.db.delete(memory)
        self.db.commit()
        return True


class ConversationRepository:
    """Persistence operations for conversations and chat messages."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, title: str = "New Chat") -> Conversation:
        conversation = Conversation(title=title[:200])
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_by_id(self, conversation_id: int) -> Conversation | None:
        return (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

    def list_all(self) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .all()
        )

    def update_title(self, conversation: Conversation, title: str) -> Conversation:
        conversation.title = title[:200]
        conversation.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def add_message(
        self,
        *,
        conversation_id: int,
        role: str,
        content: str,
        tool_metadata: str | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_metadata=tool_metadata,
        )
        self.db.add(message)
        conversation = self.get_by_id(conversation_id)
        if conversation is not None:
            conversation.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, conversation_id: int) -> list[Message]:
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
            .all()
        )
