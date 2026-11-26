"""Database repository layer with strict user_id scoping."""

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database.models import (
    Approval,
    Conversation,
    Integration,
    IntegrationCredential,
    Memory,
    Message,
    OAuthState,
    Reminder,
    Task,
    ToolExecution,
    User,
    utc_now,
)


def normalize_memory_key(raw_key: str) -> str:
    """Normalize memory keys so equivalent casing/spacing maps to one key."""
    return "_".join(raw_key.strip().lower().split())


class UserRepository:
    """Lookup and creation for LifeDesk application users."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()

    def list_all(self) -> list[User]:
        return self.db.query(User).order_by(User.id.asc()).all()

    def create(self, *, name: str, email: str, user_timezone: str = "UTC") -> User:
        user = User(name=name.strip(), email=email.strip().lower(), timezone=user_timezone)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_timezone(self, user_id: int, user_timezone: str) -> User | None:
        user = self.get_by_id(user_id)
        if user is None:
            return None
        user.timezone = user_timezone.strip()
        self.db.commit()
        self.db.refresh(user)
        return user


class TaskRepository:
    """User-scoped CRUD and search operations for Task rows."""

    def __init__(self, db: Session, user_id: int = 1) -> None:
        self.db = db
        self.user_id = user_id

    def create(
        self,
        *,
        title: str,
        description: str | None = None,
        due_date: str | None = None,
    ) -> Task:
        task = Task(
            user_id=self.user_id,
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
        stmt = self.db.query(Task).filter(Task.user_id == self.user_id)
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
        return (
            self.db.query(Task)
            .filter(Task.id == task_id, Task.user_id == self.user_id)
            .first()
        )

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


class ReminderRepository:
    """User-scoped CRUD operations for Reminder rows."""

    def __init__(self, db: Session, user_id: int = 1) -> None:
        self.db = db
        self.user_id = user_id

    def create(self, *, title: str, remind_at: str, task_id: int | None = None) -> Reminder:
        if task_id is not None:
            owned_task = (
                self.db.query(Task)
                .filter(Task.id == task_id, Task.user_id == self.user_id)
                .first()
            )
            if owned_task is None:
                raise ValueError(f"Task {task_id} was not found for this user.")
        reminder = Reminder(
            user_id=self.user_id,
            task_id=task_id,
            title=title,
            remind_at=remind_at,
            status="pending",
        )
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        return reminder

    def list_all(self, *, status: str | None = None) -> list[Reminder]:
        stmt = self.db.query(Reminder).filter(Reminder.user_id == self.user_id)
        if status:
            stmt = stmt.filter(Reminder.status == status)
        return stmt.order_by(Reminder.id.asc()).all()


class MemoryRepository:
    """User-scoped CRUD and deduplicating upsert operations for Memory rows."""

    def __init__(self, db: Session, user_id: int = 1) -> None:
        self.db = db
        self.user_id = user_id

    def list_all(self) -> list[Memory]:
        return (
            self.db.query(Memory)
            .filter(Memory.user_id == self.user_id)
            .order_by(Memory.updated_at.desc(), Memory.id.asc())
            .all()
        )

    def get_by_id(self, memory_id: int) -> Memory | None:
        return (
            self.db.query(Memory)
            .filter(Memory.id == memory_id, Memory.user_id == self.user_id)
            .first()
        )

    def get_by_key(self, raw_key: str) -> Memory | None:
        normalized = normalize_memory_key(raw_key)
        return (
            self.db.query(Memory)
            .filter(Memory.user_id == self.user_id, func.lower(Memory.key) == normalized)
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

        memory = Memory(user_id=self.user_id, key=normalized_key, value=value)
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
                .filter(
                    Memory.user_id == self.user_id,
                    func.lower(Memory.key) == normalized_key,
                    Memory.id != memory_id,
                )
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
    """User-scoped persistence operations for conversations and chat messages."""

    def __init__(self, db: Session, user_id: int = 1) -> None:
        self.db = db
        self.user_id = user_id

    def create(self, title: str = "New Chat") -> Conversation:
        conversation = Conversation(user_id=self.user_id, title=title[:200])
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_by_id(self, conversation_id: int) -> Conversation | None:
        return (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == self.user_id)
            .first()
        )

    def list_all(self) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == self.user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .all()
        )

    def add_message(
        self,
        *,
        conversation_id: int,
        role: str,
        content: str,
        tool_metadata: str | None = None,
    ) -> Message:
        conversation = self.get_by_id(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} was not found for this user.")

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_metadata=tool_metadata,
        )
        self.db.add(message)
        conversation.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, conversation_id: int) -> list[Message]:
        conversation = self.get_by_id(conversation_id)
        if conversation is None:
            return []
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
            .all()
        )


class IntegrationRepository:
    """User-scoped storage for external integrations and encrypted OAuth credentials."""

    def __init__(self, db: Session, user_id: int) -> None:
        self.db = db
        self.user_id = user_id

    def get_by_provider(self, provider: str) -> Integration | None:
        return (
            self.db.query(Integration)
            .filter(Integration.user_id == self.user_id, Integration.provider == provider)
            .first()
        )

    def list_all(self) -> list[Integration]:
        return (
            self.db.query(Integration)
            .filter(Integration.user_id == self.user_id)
            .order_by(Integration.provider.asc())
            .all()
        )

    def upsert_connection(
        self,
        *,
        provider: str,
        account_email: str | None,
        status: str,
        granted_scopes: list[str],
        encrypted_access_token: str | None,
        encrypted_refresh_token: str | None,
        token_expiry: datetime | None,
        encryption_version: str,
    ) -> Integration:
        integration = self.get_by_provider(provider)
        now = utc_now()

        if integration is None:
            integration = Integration(
                user_id=self.user_id,
                provider=provider,
                account_email=account_email,
                status=status,
                granted_scopes=json.dumps(sorted(set(granted_scopes))),
                last_connected_at=now if status == "connected" else None,
            )
            self.db.add(integration)
            self.db.flush()
        else:
            existing_scopes = set(json.loads(integration.granted_scopes or "[]"))
            merged_scopes = sorted(existing_scopes.union(granted_scopes))
            integration.account_email = account_email or integration.account_email
            integration.status = status
            integration.granted_scopes = json.dumps(merged_scopes)
            integration.updated_at = now
            if status == "connected":
                integration.last_connected_at = now

        cred = integration.credential
        if cred is None:
            cred = IntegrationCredential(
                integration_id=integration.id,
                encrypted_access_token=encrypted_access_token,
                encrypted_refresh_token=encrypted_refresh_token,
                token_expiry=token_expiry,
                encryption_version=encryption_version,
            )
            self.db.add(cred)
        else:
            if encrypted_access_token is not None:
                cred.encrypted_access_token = encrypted_access_token
            # Never overwrite an existing valid refresh token with None/empty.
            if encrypted_refresh_token:
                cred.encrypted_refresh_token = encrypted_refresh_token
            cred.token_expiry = token_expiry
            cred.encryption_version = encryption_version
            cred.updated_at = now

        self.db.commit()
        self.db.refresh(integration)
        return integration

    def update_status(self, provider: str, status: str) -> Integration | None:
        integration = self.get_by_provider(provider)
        if integration is None:
            return None
        integration.status = status
        integration.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def update_access_token(
        self,
        integration: Integration,
        *,
        encrypted_access_token: str,
        token_expiry: datetime | None,
        encryption_version: str,
    ) -> None:
        if integration.credential is None:
            return
        integration.credential.encrypted_access_token = encrypted_access_token
        integration.credential.token_expiry = token_expiry
        integration.credential.encryption_version = encryption_version
        integration.credential.updated_at = utc_now()
        self.db.commit()

    def disconnect(self, provider: str) -> bool:
        integration = self.get_by_provider(provider)
        if integration is None:
            return False
        if integration.credential is not None:
            self.db.delete(integration.credential)
        integration.status = "disconnected"
        integration.granted_scopes = "[]"
        integration.updated_at = utc_now()
        self.db.commit()
        return True


class OAuthStateRepository:
    """Stores and consumes one-time OAuth state + PKCE verifiers."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        state: str,
        user_id: int,
        service: str,
        requested_scopes: list[str],
        code_verifier: str,
        expires_at: datetime,
    ) -> OAuthState:
        record = OAuthState(
            state=state,
            user_id=user_id,
            service=service,
            requested_scopes=json.dumps(requested_scopes),
            code_verifier=code_verifier,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def consume(self, state: str) -> OAuthState | None:
        """Atomically look up and remove a one-time OAuth state record."""
        record = self.db.query(OAuthState).filter(OAuthState.state == state).first()
        if record is None:
            return None
        self.db.delete(record)
        self.db.commit()
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < utc_now():
            return None
        return record


class ApprovalRepository:
    """User-scoped persistence for human-in-the-loop approvals."""

    def __init__(self, db: Session, user_id: int) -> None:
        self.db = db
        self.user_id = user_id

    def create(
        self,
        *,
        conversation_id: int | None,
        provider: str,
        tool_name: str,
        action_type: str,
        action_payload: dict[str, Any],
        summary: str,
        expires_at: datetime,
    ) -> Approval:
        approval = Approval(
            user_id=self.user_id,
            conversation_id=conversation_id,
            provider=provider,
            tool_name=tool_name,
            action_type=action_type,
            action_payload=json.dumps(action_payload, sort_keys=True),
            summary=summary,
            status="PENDING",
            expires_at=expires_at,
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def get_by_id(self, approval_id: int) -> Approval | None:
        approval = (
            self.db.query(Approval)
            .filter(Approval.id == approval_id, Approval.user_id == self.user_id)
            .first()
        )
        if approval is not None:
            self._expire_if_needed(approval)
        return approval

    def list_all(self, *, status: str | None = None) -> list[Approval]:
        stmt = self.db.query(Approval).filter(Approval.user_id == self.user_id)
        if status:
            stmt = stmt.filter(Approval.status == status)
        items = stmt.order_by(Approval.id.desc()).all()
        for item in items:
            self._expire_if_needed(item)
        if status:
            return [item for item in items if item.status == status]
        return items

    def _expire_if_needed(self, approval: Approval) -> None:
        if approval.status != "PENDING":
            return
        exp = approval.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < utc_now():
            approval.status = "EXPIRED"
            self.db.commit()
            self.db.refresh(approval)

    def transition_to_approved(self, approval_id: int) -> Approval | None:
        """Atomically transition PENDING -> APPROVED to prevent double execution."""
        approval = self.get_by_id(approval_id)
        if approval is None or approval.status != "PENDING":
            return None
        updated_rows = (
            self.db.query(Approval)
            .filter(
                Approval.id == approval_id,
                Approval.user_id == self.user_id,
                Approval.status == "PENDING",
            )
            .update(
                {"status": "APPROVED", "approved_at": utc_now()},
                synchronize_session=False,
            )
        )
        self.db.commit()
        if updated_rows == 0:
            return None
        return self.get_by_id(approval_id)

    def mark_executed(self, approval_id: int, result: dict[str, Any]) -> Approval | None:
        approval = self.get_by_id(approval_id)
        if approval is None:
            return None
        approval.status = "EXECUTED"
        approval.executed_at = utc_now()
        approval.execution_result = json.dumps(result)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def mark_failed(self, approval_id: int, error_message: str) -> Approval | None:
        approval = self.get_by_id(approval_id)
        if approval is None:
            return None
        approval.status = "FAILED"
        approval.executed_at = utc_now()
        approval.execution_result = json.dumps({"status": "error", "error": error_message})
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def reject(self, approval_id: int) -> Approval | None:
        approval = self.get_by_id(approval_id)
        if approval is None:
            return None
        if approval.status != "PENDING":
            return approval
        approval.status = "REJECTED"
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def cancel_matching_pending_for_conversation(
        self,
        *,
        conversation_id: int | None,
        tool_name: str,
        new_payload: dict[str, Any],
    ) -> int:
        """Cancel older PENDING approvals only when the new proposal supersedes the same target."""
        if conversation_id is None:
            return 0
        pending = (
            self.db.query(Approval)
            .filter(
                Approval.user_id == self.user_id,
                Approval.conversation_id == conversation_id,
                Approval.tool_name == tool_name,
                Approval.status == "PENDING",
            )
            .all()
        )
        cancelled = 0
        new_title = str(new_payload.get("title") or "").strip().lower()
        new_start = str(new_payload.get("start_datetime") or "").strip()
        new_event_id = str(new_payload.get("event_id") or "").strip()

        for row in pending:
            try:
                old_payload = json.loads(row.action_payload)
            except Exception:
                old_payload = {}

            is_same_target = False
            if tool_name == "calendar_create_event":
                old_title = str(old_payload.get("title") or "").strip().lower()
                old_start = str(old_payload.get("start_datetime") or "").strip()
                if (new_title and old_title == new_title) or (new_start and old_start == new_start):
                    is_same_target = True
            elif tool_name in ("calendar_update_event", "calendar_delete_event"):
                old_event_id = str(old_payload.get("event_id") or "").strip()
                if new_event_id and old_event_id == new_event_id:
                    is_same_target = True

            if is_same_target:
                row.status = "CANCELLED"
                cancelled += 1

        if cancelled:
            self.db.commit()
        return cancelled


class ToolExecutionRepository:
    """Stores safe audit records of native and MCP tool invocations."""

    def __init__(self, db: Session, user_id: int) -> None:
        self.db = db
        self.user_id = user_id

    def record(
        self,
        *,
        conversation_id: int | None,
        tool_name: str,
        tool_source: str,
        status: str,
        duration_ms: int,
        safe_error_summary: str | None = None,
    ) -> ToolExecution:
        entry = ToolExecution(
            user_id=self.user_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            tool_source=tool_source,
            status=status,
            duration_ms=duration_ms,
            safe_error_summary=safe_error_summary[:300] if safe_error_summary else None,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_recent(self, limit: int = 50) -> list[ToolExecution]:
        return (
            self.db.query(ToolExecution)
            .filter(ToolExecution.user_id == self.user_id)
            .order_by(ToolExecution.id.desc())
            .limit(limit)
            .all()
        )
