"""Unified tool abstraction combining native internal tools and external MCP tools."""

from dataclasses import dataclass, field
import logging
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from app.agent.tool_registry import TOOL_REGISTRY as NATIVE_TOOL_REGISTRY
from app.agent.tool_registry import execute_registered_tool
from app.approvals.service import ApprovalService
from app.config import Settings
from app.database.models import User
from app.database.repositories import ToolExecutionRepository
from app.integrations.google_oauth import (
    CALENDAR_EVENTS_SCOPE,
    CALENDAR_READ_SCOPE,
    GMAIL_COMPOSE_SCOPE,
    GMAIL_READ_SCOPE,
    GMAIL_SEND_SCOPE,
    GoogleOAuthConfigError,
    GoogleOAuthService,
    IntegrationAuthError,
    IntegrationNotConnectedError,
)
from app.mcp_client.client import MCPClientError, MCPClientManager
from app.schemas.approval import ApprovalOut
from app.security.crypto import TokenEncryptionError

logger = logging.getLogger(__name__)


# --- Pydantic Validation Schemas for MCP Tools ---


class GmailSearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(..., min_length=1, max_length=300)
    max_results: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        c = v.strip()
        if not c:
            raise ValueError("Search query cannot be empty.")
        return c


class GmailGetEmailArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(..., min_length=1, max_length=200)


class GmailListRecentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_results: int = Field(default=5, ge=1, le=20)


class GmailGetThreadArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: str = Field(..., min_length=1, max_length=200)


class GmailCreateDraftArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: str = Field(..., min_length=3, max_length=320)
    subject: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1, max_length=10000)


class GmailSendEmailArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: str = Field(..., min_length=3, max_length=320)
    subject: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1, max_length=10000)
    thread_id: str | None = Field(default=None, max_length=200)


class CalendarListCalendarsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CalendarWindowArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_datetime: str = Field(..., min_length=4, max_length=100)
    end_datetime: str = Field(..., min_length=4, max_length=100)


class CalendarGetEventArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(..., min_length=1, max_length=200)


class CalendarCreateEventArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1, max_length=300)
    start_datetime: str = Field(..., min_length=4, max_length=100)
    end_datetime: str = Field(..., min_length=4, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    attendees: list[str] | None = Field(default=None, max_length=50)

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        c = v.strip()
        if not c:
            raise ValueError("Event title cannot be empty.")
        return c


class CalendarUpdateEventArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(..., min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    start_datetime: str | None = Field(default=None, min_length=4, max_length=100)
    end_datetime: str | None = Field(default=None, min_length=4, max_length=100)
    attendees: list[str] | None = Field(default=None, max_length=50)


class CalendarDeleteEventArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(..., min_length=1, max_length=200)


@dataclass(frozen=True)
class UnifiedToolDefinition:
    """Metadata preserved for every native or MCP tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    source: str  # native | mcp
    provider: str  # internal | gmail | calendar
    input_schema: type[BaseModel]
    required_scopes: list[str] = field(default_factory=list)
    requires_approval: bool = False
    action_type: str = ""

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _build_mcp_tool_definitions() -> dict[str, UnifiedToolDefinition]:
    defs = [
        UnifiedToolDefinition(
            name="gmail_search_emails",
            description="Search the user's Gmail inbox using Gmail search syntax (e.g. 'from:rahul', 'is:unread').",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query."},
                    "max_results": {"type": "integer", "description": "Max emails to return (1-20)."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="gmail",
            input_schema=GmailSearchArgs,
            required_scopes=[GMAIL_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="gmail_get_email",
            description="Retrieve the subject, metadata, and body of a specific Gmail message by message_id.",
            parameters={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message ID."},
                },
                "required": ["message_id"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="gmail",
            input_schema=GmailGetEmailArgs,
            required_scopes=[GMAIL_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="gmail_list_recent_emails",
            description="List the user's most recent Gmail inbox messages.",
            parameters={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Max emails to return (1-20)."},
                },
                "required": [],
                "additionalProperties": False,
            },
            source="mcp",
            provider="gmail",
            input_schema=GmailListRecentArgs,
            required_scopes=[GMAIL_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="gmail_get_thread",
            description="Retrieve all messages in a Gmail thread by thread_id.",
            parameters={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Gmail thread ID."},
                },
                "required": ["thread_id"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="gmail",
            input_schema=GmailGetThreadArgs,
            required_scopes=[GMAIL_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="gmail_create_draft",
            description="Create a Gmail draft without sending it.",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address."},
                    "subject": {"type": "string", "description": "Email subject."},
                    "body": {"type": "string", "description": "Email body text."},
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="gmail",
            input_schema=GmailCreateDraftArgs,
            required_scopes=[GMAIL_COMPOSE_SCOPE],
        ),
        UnifiedToolDefinition(
            name="gmail_send_email",
            description=(
                "Propose sending an email via Gmail. Always requires explicit human approval "
                "before the email is actually sent."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address."},
                    "subject": {"type": "string", "description": "Email subject."},
                    "body": {"type": "string", "description": "Exact email body to send."},
                    "thread_id": {"type": "string", "description": "Optional Gmail thread ID for replies."},
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="gmail",
            input_schema=GmailSendEmailArgs,
            required_scopes=[GMAIL_SEND_SCOPE],
            requires_approval=True,
            action_type="send_email",
        ),
        UnifiedToolDefinition(
            name="calendar_list_calendars",
            description="List the user's Google Calendars.",
            parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            source="mcp",
            provider="calendar",
            input_schema=CalendarListCalendarsArgs,
            required_scopes=[CALENDAR_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="calendar_list_events",
            description="List Google Calendar events between start_datetime and end_datetime (ISO-8601).",
            parameters={
                "type": "object",
                "properties": {
                    "start_datetime": {"type": "string", "description": "ISO-8601 start timestamp."},
                    "end_datetime": {"type": "string", "description": "ISO-8601 end timestamp."},
                },
                "required": ["start_datetime", "end_datetime"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="calendar",
            input_schema=CalendarWindowArgs,
            required_scopes=[CALENDAR_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="calendar_get_event",
            description="Get details for a specific Google Calendar event by event_id.",
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Google Calendar event ID."},
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="calendar",
            input_schema=CalendarGetEventArgs,
            required_scopes=[CALENDAR_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="calendar_check_availability",
            description="Check free and busy slots in the user's Google Calendar for a time window (ISO-8601).",
            parameters={
                "type": "object",
                "properties": {
                    "start_datetime": {"type": "string", "description": "ISO-8601 start timestamp."},
                    "end_datetime": {"type": "string", "description": "ISO-8601 end timestamp."},
                },
                "required": ["start_datetime", "end_datetime"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="calendar",
            input_schema=CalendarWindowArgs,
            required_scopes=[CALENDAR_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="calendar_find_conflicts",
            description="Find any existing Google Calendar events overlapping start_datetime and end_datetime.",
            parameters={
                "type": "object",
                "properties": {
                    "start_datetime": {"type": "string", "description": "ISO-8601 start timestamp."},
                    "end_datetime": {"type": "string", "description": "ISO-8601 end timestamp."},
                },
                "required": ["start_datetime", "end_datetime"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="calendar",
            input_schema=CalendarWindowArgs,
            required_scopes=[CALENDAR_READ_SCOPE],
        ),
        UnifiedToolDefinition(
            name="calendar_create_event",
            description=(
                "Propose creating a Google Calendar event. Always check conflicts first and requires "
                "explicit user approval before the event is actually created."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title."},
                    "start_datetime": {"type": "string", "description": "ISO-8601 start datetime."},
                    "end_datetime": {"type": "string", "description": "ISO-8601 end datetime."},
                    "description": {"type": "string", "description": "Optional event description."},
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional attendee email addresses.",
                    },
                },
                "required": ["title", "start_datetime", "end_datetime"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="calendar",
            input_schema=CalendarCreateEventArgs,
            required_scopes=[CALENDAR_EVENTS_SCOPE],
            requires_approval=True,
            action_type="create_calendar_event",
        ),
        UnifiedToolDefinition(
            name="calendar_update_event",
            description=(
                "Propose updating an existing Google Calendar event. Requires explicit user approval."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to update."},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "start_datetime": {"type": "string"},
                    "end_datetime": {"type": "string"},
                    "attendees": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="calendar",
            input_schema=CalendarUpdateEventArgs,
            required_scopes=[CALENDAR_EVENTS_SCOPE],
            requires_approval=True,
            action_type="update_calendar_event",
        ),
        UnifiedToolDefinition(
            name="calendar_delete_event",
            description=(
                "Propose deleting a Google Calendar event by event_id. Requires explicit user approval."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to delete."},
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
            source="mcp",
            provider="calendar",
            input_schema=CalendarDeleteEventArgs,
            required_scopes=[CALENDAR_EVENTS_SCOPE],
            requires_approval=True,
            action_type="delete_calendar_event",
        ),
    ]
    return {d.name: d for d in defs}


def _summarize_approval_action(tool_name: str, payload: dict[str, Any]) -> str:
    if tool_name == "gmail_send_email":
        return f"Send email to {payload.get('to')} — Subject: {payload.get('subject')}"
    if tool_name == "calendar_create_event":
        return (
            f"Create calendar event '{payload.get('title')}' "
            f"({payload.get('start_datetime')} to {payload.get('end_datetime')})"
        )
    if tool_name == "calendar_update_event":
        return f"Update calendar event {payload.get('event_id')}"
    if tool_name == "calendar_delete_event":
        return f"Delete calendar event {payload.get('event_id')}"
    return f"Execute {tool_name}"


def _demo_mode_response(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Explicitly labeled demo-mode sample responses when DEMO_MODE=true and OAuth is unset."""
    if tool_name in ("gmail_search_emails", "gmail_list_recent_emails"):
        return {
            "status": "ok",
            "demo_mode": True,
            "notice": "[DEMO MODE] Google OAuth is not configured; returning sample demo email data.",
            "emails": [
                {
                    "message_id": "demo_msg_1",
                    "thread_id": "demo_thread_1",
                    "from": "Rahul <rahul@example.com>",
                    "subject": "Tomorrow's Project Discussion at 3:00 PM",
                    "date": "2026-11-26",
                    "snippet": "Hi, let's meet tomorrow at 3:00 PM for 30 minutes to discuss the milestone.",
                }
            ],
        }
    if tool_name in ("gmail_get_email", "gmail_get_thread"):
        return {
            "status": "ok",
            "demo_mode": True,
            "notice": "[DEMO MODE] Sample email body (not real Gmail data).",
            "email": {
                "message_id": payload.get("message_id", "demo_msg_1"),
                "from": "Rahul <rahul@example.com>",
                "subject": "Tomorrow's Project Discussion at 3:00 PM",
                "body": "Hi, let's meet tomorrow from 3:00 PM to 3:30 PM UTC.",
            },
        }
    if tool_name == "gmail_create_draft":
        return {
            "status": "draft_created",
            "demo_mode": True,
            "draft_id": "demo_draft_1",
            "to": payload.get("to"),
            "subject": payload.get("subject"),
        }
    if tool_name in ("calendar_list_events", "calendar_check_availability", "calendar_find_conflicts"):
        return {
            "status": "ok",
            "demo_mode": True,
            "notice": "[DEMO MODE] Sample calendar state (not real Google Calendar data).",
            "is_available": True,
            "has_conflicts": False,
            "events": [],
            "conflicts": [],
            "free_slots": [
                {
                    "start": payload.get("start_datetime", ""),
                    "end": payload.get("end_datetime", ""),
                }
            ],
        }
    return {
        "status": "ok",
        "demo_mode": True,
        "notice": f"[DEMO MODE] Simulated read for {tool_name}.",
    }


class UnifiedToolExecutor:
    """Single registry and execution boundary across native and MCP tools."""

    def __init__(
        self,
        settings: Settings,
        oauth_service: GoogleOAuthService | None = None,
        mcp_client: MCPClientManager | None = None,
        approval_service: ApprovalService | None = None,
    ) -> None:
        self.settings = settings
        self.oauth_service = oauth_service or GoogleOAuthService(settings)
        self.mcp_client = mcp_client or MCPClientManager()
        self.approval_service = approval_service or ApprovalService(
            settings, self.oauth_service, self.mcp_client
        )

        self._tools: dict[str, UnifiedToolDefinition] = {}
        for name, native_tool in NATIVE_TOOL_REGISTRY.items():
            self._tools[name] = UnifiedToolDefinition(
                name=native_tool.name,
                description=native_tool.description,
                parameters=native_tool.parameters,
                source="native",
                provider="internal",
                input_schema=native_tool.input_schema,
            )
        self._tools.update(_build_mcp_tool_definitions())

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Return OpenAI-formatted tool definitions for all native and MCP tools."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def get_definition(self, tool_name: str) -> UnifiedToolDefinition | None:
        return self._tools.get(tool_name)

    def execute(
        self,
        db: Session,
        *,
        user: User,
        conversation_id: int | None,
        tool_name: str,
        raw_arguments: Any,
    ) -> tuple[bool, dict[str, Any], str, ApprovalOut | None]:
        """Validate, authorize, stage approval if needed, or execute a registered tool."""
        tool_def = self._tools.get(tool_name)
        exec_repo = ToolExecutionRepository(db, user_id=user.id)
        started = time.perf_counter()

        if tool_def is None:
            err = f"Tool '{tool_name}' is not registered and cannot be executed."
            exec_repo.record(
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_source="unknown",
                status="error",
                duration_ms=0,
                safe_error_summary=err,
            )
            return False, {"status": "error", "error": err}, "unknown", None

        if not isinstance(raw_arguments, dict):
            err = f"Arguments for '{tool_name}' must be a JSON object."
            exec_repo.record(
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_source=tool_def.source,
                status="error",
                duration_ms=0,
                safe_error_summary=err,
            )
            return False, {"status": "error", "error": err}, tool_def.source, None

        try:
            validated_model = tool_def.input_schema.model_validate(raw_arguments)
        except ValidationError as exc:
            err = f"Invalid arguments for '{tool_name}': {exc.errors()}"
            exec_repo.record(
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_source=tool_def.source,
                status="error",
                duration_ms=0,
                safe_error_summary="Argument validation failed",
            )
            return False, {"status": "error", "error": err}, tool_def.source, None

        validated_dict = validated_model.model_dump(exclude_none=True)

        # Native tools run internally through the registered Python handlers.
        if tool_def.source == "native":
            ok, res = execute_registered_tool(
                db,
                tool_name,
                raw_arguments,
                user_id=user.id,
                conversation_id=conversation_id,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            staged_approval: ApprovalOut | None = None
            log_status = "success" if ok else "error"
            if res.get("status") == "approval_required" and isinstance(res.get("approval"), dict):
                log_status = "approval_required"
                staged_approval = ApprovalOut.model_validate(res["approval"])

            exec_repo.record(
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_source="native",
                status=log_status,
                duration_ms=duration_ms,
                safe_error_summary=str(res.get("error"))[:300] if not ok else None,
            )
            return ok, res, "native", staged_approval

        # MCP tools: check per-user OAuth authorization first.
        demo_fallback = self.settings.demo_mode and not self.oauth_service.is_oauth_configured()

        if not demo_fallback:
            try:
                access_token = self.oauth_service.get_valid_access_token(
                    db,
                    user_id=user.id,
                    provider=tool_def.provider,  # type: ignore[arg-type]
                    required_scopes=tool_def.required_scopes,
                )
            except IntegrationNotConnectedError as exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                exec_repo.record(
                    conversation_id=conversation_id,
                    tool_name=tool_name,
                    tool_source="mcp",
                    status="error",
                    duration_ms=duration_ms,
                    safe_error_summary="Integration not connected",
                )
                return (
                    False,
                    {
                        "status": "error",
                        "error_code": "integration_required",
                        "provider": tool_def.provider,
                        "error": str(exc),
                    },
                    "mcp",
                    None,
                )
            except (IntegrationAuthError, GoogleOAuthConfigError, TokenEncryptionError) as exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                exec_repo.record(
                    conversation_id=conversation_id,
                    tool_name=tool_name,
                    tool_source="mcp",
                    status="error",
                    duration_ms=duration_ms,
                    safe_error_summary="Integration auth/config error",
                )
                return (
                    False,
                    {
                        "status": "error",
                        "error_code": "integration_auth_error",
                        "provider": tool_def.provider,
                        "error": str(exc),
                    },
                    "mcp",
                    None,
                )
        else:
            access_token = ""

        # Approval-gated MCP actions NEVER execute immediately inside the LLM loop.
        if tool_def.requires_approval:
            summary = _summarize_approval_action(tool_name, validated_dict)
            approval_out = self.approval_service.stage_approval(
                db,
                user_id=user.id,
                conversation_id=conversation_id,
                provider=tool_def.provider,
                tool_name=tool_name,
                action_type=tool_def.action_type,
                action_payload=validated_dict,
                summary=summary,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            exec_repo.record(
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_source="mcp",
                status="approval_required",
                duration_ms=duration_ms,
            )
            return (
                True,
                {
                    "status": "approval_required",
                    "approval_id": approval_out.id,
                    "summary": summary,
                    "action_payload": validated_dict,
                    "message": (
                        "This action requires explicit user approval and has been queued in the UI. "
                        "Tell the user what is proposed and ask them to approve or reject it. "
                        "Do NOT claim it has already been sent or created."
                    ),
                },
                "mcp",
                approval_out,
            )

        # Safe read / draft MCP tool invocation via isolated per-user MCP STDIO session.
        if demo_fallback:
            res = _demo_mode_response(tool_name, validated_dict)
            duration_ms = int((time.perf_counter() - started) * 1000)
            exec_repo.record(
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_source="mcp",
                status="success",
                duration_ms=duration_ms,
            )
            return True, res, "mcp", None

        try:
            res = self.mcp_client.call_tool(
                provider=tool_def.provider,
                tool_name=tool_name,
                arguments=validated_dict,
                access_token=access_token,
                user_timezone=user.timezone,
            )
        except MCPClientError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            exec_repo.record(
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_source="mcp",
                status="error",
                duration_ms=duration_ms,
                safe_error_summary=str(exc),
            )
            return False, {"status": "error", "error": str(exc)}, "mcp", None

        ok = res.get("status") != "error"
        duration_ms = int((time.perf_counter() - started) * 1000)
        exec_repo.record(
            conversation_id=conversation_id,
            tool_name=tool_name,
            tool_source="mcp",
            status="success" if ok else "error",
            duration_ms=duration_ms,
            safe_error_summary=str(res.get("error"))[:300] if not ok else None,
        )
        return ok, res, "mcp", None
