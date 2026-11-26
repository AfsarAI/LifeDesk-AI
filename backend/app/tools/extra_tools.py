"""Additional native tools: reminders, user preferences, and explicit approval staging."""

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.database.models import utc_now
from app.database.repositories import (
    ApprovalRepository,
    MemoryRepository,
    ReminderRepository,
    UserRepository,
)
from app.schemas.approval import ApprovalOut, RequestUserApprovalArgs
from app.schemas.task import (
    CreateReminderArgs,
    GetUserPreferencesArgs,
    ListRemindersArgs,
    ReminderOut,
)


def create_reminder_tool(
    db: Session,
    args: CreateReminderArgs,
    *,
    user_id: int = 1,
) -> dict[str, Any]:
    """Create and persist a reminder scoped to the authenticated user."""
    repo = ReminderRepository(db, user_id=user_id)
    try:
        reminder = repo.create(
            title=args.title,
            remind_at=args.remind_at,
            task_id=args.task_id,
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}

    return {
        "status": "created",
        "reminder": ReminderOut.model_validate(reminder).model_dump(mode="json"),
    }


def list_reminders_tool(
    db: Session,
    args: ListRemindersArgs,
    *,
    user_id: int = 1,
) -> dict[str, Any]:
    """List reminders belonging to the authenticated user."""
    repo = ReminderRepository(db, user_id=user_id)
    reminders = repo.list_all(status=args.status)
    return {
        "status": "ok",
        "count": len(reminders),
        "reminders": [
            ReminderOut.model_validate(r).model_dump(mode="json") for r in reminders
        ],
    }


def get_user_preferences_tool(
    db: Session,
    _args: GetUserPreferencesArgs,
    *,
    user_id: int = 1,
) -> dict[str, Any]:
    """Return the authenticated user's profile timezone and saved preference memories."""
    user = UserRepository(db).get_by_id(user_id)
    memories = MemoryRepository(db, user_id=user_id).list_all()
    prefs = {m.key: m.value for m in memories}
    return {
        "status": "ok",
        "timezone": user.timezone if user else "UTC",
        "name": user.name if user else None,
        "preferences": prefs,
    }


def request_user_approval_tool(
    db: Session,
    args: RequestUserApprovalArgs,
    *,
    user_id: int = 1,
    conversation_id: int | None = None,
) -> dict[str, Any]:
    """Stage a reusable PENDING approval record for user confirmation."""
    import json

    repo = ApprovalRepository(db, user_id=user_id)
    approval = repo.create(
        conversation_id=conversation_id,
        provider=args.provider,
        tool_name=args.tool_name,
        action_type=args.action_type,
        action_payload=args.action_payload,
        summary=args.summary,
        expires_at=utc_now() + timedelta(minutes=30),
    )
    out = ApprovalOut(
        id=approval.id,
        user_id=approval.user_id,
        conversation_id=approval.conversation_id,
        provider=approval.provider,
        tool_name=approval.tool_name,
        action_type=approval.action_type,
        action_payload=json.loads(approval.action_payload),
        summary=approval.summary,
        status=approval.status,
        expires_at=approval.expires_at,
        created_at=approval.created_at,
        approved_at=approval.approved_at,
        executed_at=approval.executed_at,
        execution_result=None,
    )
    return {
        "status": "approval_required",
        "approval_id": approval.id,
        "approval": out.model_dump(mode="json"),
        "message": "Action staged for explicit user approval. Wait for user confirmation.",
    }
