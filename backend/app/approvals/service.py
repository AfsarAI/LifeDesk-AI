"""Reusable human-in-the-loop approval service for consequential actions."""

from datetime import timedelta
import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import Approval, User, utc_now
from app.database.repositories import ApprovalRepository, ToolExecutionRepository
from app.integrations.google_oauth import (
    CALENDAR_EVENTS_SCOPE,
    GMAIL_SEND_SCOPE,
    GoogleOAuthService,
    IntegrationAuthError,
    IntegrationNotConnectedError,
)
from app.mcp_client.client import MCPClientError, MCPClientManager
from app.schemas.approval import ApprovalOut

logger = logging.getLogger(__name__)

DEFAULT_APPROVAL_TTL_MINUTES = 30

# Explicit mapping from approval tool_name -> required OAuth scopes and MCP provider.
APPROVAL_MCP_POLICIES: dict[str, tuple[str, list[str]]] = {
    "gmail_send_email": ("gmail", [GMAIL_SEND_SCOPE]),
    "calendar_create_event": ("calendar", [CALENDAR_EVENTS_SCOPE]),
    "calendar_update_event": ("calendar", [CALENDAR_EVENTS_SCOPE]),
    "calendar_delete_event": ("calendar", [CALENDAR_EVENTS_SCOPE]),
}


class ApprovalError(Exception):
    """Raised on invalid approval state transitions or authorization failures."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def serialize_approval(approval: Approval) -> ApprovalOut:
    """Convert an ORM Approval row into an ApprovalOut schema."""
    payload: dict[str, Any] = {}
    try:
        decoded = json.loads(approval.action_payload)
        if isinstance(decoded, dict):
            payload = decoded
    except Exception:
        payload = {}

    exec_result: dict[str, Any] | None = None
    if approval.execution_result:
        try:
            decoded_res = json.loads(approval.execution_result)
            if isinstance(decoded_res, dict):
                exec_result = decoded_res
        except Exception:
            exec_result = None

    return ApprovalOut(
        id=approval.id,
        user_id=approval.user_id,
        conversation_id=approval.conversation_id,
        provider=approval.provider,
        tool_name=approval.tool_name,
        action_type=approval.action_type,
        action_payload=payload,
        summary=approval.summary,
        status=approval.status,
        expires_at=approval.expires_at,
        created_at=approval.created_at,
        approved_at=approval.approved_at,
        executed_at=approval.executed_at,
        execution_result=exec_result,
    )


class ApprovalService:
    """Stages, validates, approves, executes, and rejects sensitive actions."""

    def __init__(
        self,
        settings: Settings,
        oauth_service: GoogleOAuthService | None = None,
        mcp_client: MCPClientManager | None = None,
    ) -> None:
        self.settings = settings
        self.oauth_service = oauth_service or GoogleOAuthService(settings)
        self.mcp_client = mcp_client or MCPClientManager()

    def stage_approval(
        self,
        db: Session,
        *,
        user_id: int,
        conversation_id: int | None,
        provider: str,
        tool_name: str,
        action_type: str,
        action_payload: dict[str, Any],
        summary: str,
    ) -> ApprovalOut:
        """Create a PENDING approval bound strictly to user_id and exact action_payload."""
        repo = ApprovalRepository(db, user_id=user_id)
        if tool_name in ("calendar_create_event", "calendar_update_event", "calendar_delete_event"):
            repo.cancel_matching_pending_for_conversation(
                conversation_id=conversation_id,
                tool_name=tool_name,
                new_payload=action_payload,
            )
        approval = repo.create(
            conversation_id=conversation_id,
            provider=provider,
            tool_name=tool_name,
            action_type=action_type,
            action_payload=action_payload,
            summary=summary,
            expires_at=utc_now() + timedelta(minutes=DEFAULT_APPROVAL_TTL_MINUTES),
        )
        logger.info(
            "approval_staged id=%s user_id=%s tool=%s",
            approval.id,
            user_id,
            tool_name,
        )
        return serialize_approval(approval)

    def approve_and_execute(
        self,
        db: Session,
        *,
        user: User,
        approval_id: int,
    ) -> ApprovalOut:
        """Verify ownership, transition PENDING -> APPROVED, and execute the exact payload."""
        repo = ApprovalRepository(db, user_id=user.id)
        existing = repo.get_by_id(approval_id)
        if existing is None:
            raise ApprovalError(f"Approval {approval_id} was not found.", status_code=404)

        if existing.status == "EXPIRED":
            raise ApprovalError("This approval request has expired.", status_code=410)
        if existing.status != "PENDING":
            raise ApprovalError(
                f"Approval {approval_id} is already '{existing.status}' and cannot be re-executed.",
                status_code=409,
            )

        transitioned = repo.transition_to_approved(approval_id)
        if transitioned is None:
            raise ApprovalError(
                f"Approval {approval_id} could not be claimed for execution.",
                status_code=409,
            )

        payload = json.loads(transitioned.action_payload)
        exec_repo = ToolExecutionRepository(db, user_id=user.id)
        started = time.perf_counter()

        try:
            policy = APPROVAL_MCP_POLICIES.get(transitioned.tool_name)
            if policy is not None:
                provider_name, required_scopes = policy
                if self.settings.demo_mode and not self.oauth_service.is_oauth_configured():
                    result = {
                        "status": "executed_demo",
                        "demo_mode": True,
                        "tool_name": transitioned.tool_name,
                        "message": f"[DEMO MODE] Simulated execution of {transitioned.tool_name}.",
                        "payload": payload,
                    }
                else:
                    access_token = self.oauth_service.get_valid_access_token(
                        db,
                        user_id=user.id,
                        provider=provider_name,  # type: ignore[arg-type]
                        required_scopes=required_scopes,
                    )
                    result = self.mcp_client.call_tool(
                        provider=provider_name,
                        tool_name=transitioned.tool_name,
                        arguments=payload,
                        access_token=access_token,
                        user_timezone=user.timezone,
                    )
            else:
                result = {
                    "status": "approved",
                    "tool_name": transitioned.tool_name,
                    "message": "Custom approval confirmed by user.",
                }

            duration_ms = int((time.perf_counter() - started) * 1000)
            if result.get("status") == "error":
                err_msg = str(result.get("error") or "Execution failed.")
                failed = repo.mark_failed(approval_id, err_msg)
                exec_repo.record(
                    conversation_id=transitioned.conversation_id,
                    tool_name=transitioned.tool_name,
                    tool_source="mcp" if policy else "native",
                    status="error",
                    duration_ms=duration_ms,
                    safe_error_summary=err_msg,
                )
                return serialize_approval(failed or transitioned)

            done = repo.mark_executed(approval_id, result)
            exec_repo.record(
                conversation_id=transitioned.conversation_id,
                tool_name=transitioned.tool_name,
                tool_source="mcp" if policy else "native",
                status="success",
                duration_ms=duration_ms,
            )
            logger.info("approval_executed id=%s user_id=%s", approval_id, user.id)
            return serialize_approval(done or transitioned)

        except (IntegrationNotConnectedError, IntegrationAuthError, MCPClientError) as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            failed = repo.mark_failed(approval_id, str(exc))
            exec_repo.record(
                conversation_id=transitioned.conversation_id,
                tool_name=transitioned.tool_name,
                tool_source="mcp",
                status="error",
                duration_ms=duration_ms,
                safe_error_summary=str(exc),
            )
            return serialize_approval(failed or transitioned)

    def reject(self, db: Session, *, user_id: int, approval_id: int) -> ApprovalOut:
        """Reject a PENDING approval owned by user_id."""
        repo = ApprovalRepository(db, user_id=user_id)
        existing = repo.get_by_id(approval_id)
        if existing is None:
            raise ApprovalError(f"Approval {approval_id} was not found.", status_code=404)
        if existing.status != "PENDING":
            raise ApprovalError(
                f"Approval {approval_id} is already '{existing.status}'.",
                status_code=409,
            )
        rejected = repo.reject(approval_id)
        assert rejected is not None
        logger.info("approval_rejected id=%s user_id=%s", approval_id, user_id)
        return serialize_approval(rejected)
