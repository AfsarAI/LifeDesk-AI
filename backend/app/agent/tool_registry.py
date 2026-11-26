"""Native tool registry and safe dispatcher for internal LifeDesk capabilities."""

from dataclasses import dataclass
import inspect
import logging
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.schemas.approval import RequestUserApprovalArgs
from app.schemas.memory import RetrieveMemoryArgs, SaveMemoryArgs
from app.schemas.task import (
    CompleteTaskArgs,
    CreateReminderArgs,
    CreateTaskArgs,
    GetUserPreferencesArgs,
    ListRemindersArgs,
    ListTasksArgs,
    SearchTasksArgs,
    UpdateTaskArgs,
)
from app.tools.extra_tools import (
    create_reminder_tool,
    get_user_preferences_tool,
    list_reminders_tool,
    request_user_approval_tool,
)
from app.tools.memory_tools import retrieve_memory_tool, save_memory_tool
from app.tools.task_tools import (
    complete_task_tool,
    create_task_tool,
    list_tasks_tool,
    search_tasks_tool,
    update_task_tool,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegisteredTool:
    """Definition and handler for an explicitly allowed native agent tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    input_schema: type[BaseModel]
    handler: Callable[..., dict[str, Any]]

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI Chat Completions tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# Security boundary: only native tools registered here may be executed internally.
TOOL_REGISTRY: dict[str, RegisteredTool] = {
    "create_task": RegisteredTool(
        name="create_task",
        description=(
            "Create a new LifeDesk task in the database. Use only when the user clearly asks to "
            "create, add, or schedule a task and provides a task title."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Concise title of the task."},
                "due_date": {
                    "type": ["string", "null"],
                    "description": "Optional due date or deadline (e.g., '2026-11-30' or 'tomorrow').",
                },
                "description": {
                    "type": ["string", "null"],
                    "description": "Optional extra details about the task.",
                },
            },
            "required": ["title"],
            "additionalProperties": False,
        },
        input_schema=CreateTaskArgs,
        handler=create_task_tool,
    ),
    "list_tasks": RegisteredTool(
        name="list_tasks",
        description="List stored LifeDesk tasks, optionally filtered by status ('pending' or 'completed').",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": ["string", "null"],
                    "enum": ["pending", "completed", None],
                    "description": "Optional status filter. Omit to list all tasks.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        input_schema=ListTasksArgs,
        handler=list_tasks_tool,
    ),
    "update_task": RegisteredTool(
        name="update_task",
        description="Update the title, due_date, or description of an existing task by its numeric task_id.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Numeric ID of the task to update."},
                "title": {"type": ["string", "null"], "description": "Updated task title."},
                "due_date": {"type": ["string", "null"], "description": "Updated due date."},
                "description": {"type": ["string", "null"], "description": "Updated task description."},
            },
            "required": ["task_id"],
            "additionalProperties": False,
        },
        input_schema=UpdateTaskArgs,
        handler=update_task_tool,
    ),
    "complete_task": RegisteredTool(
        name="complete_task",
        description="Mark an existing task as completed using its numeric task_id.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "Numeric ID of the task to mark as completed.",
                },
            },
            "required": ["task_id"],
            "additionalProperties": False,
        },
        input_schema=CompleteTaskArgs,
        handler=complete_task_tool,
    ),
    "search_tasks": RegisteredTool(
        name="search_tasks",
        description="Search LifeDesk tasks whose title or description matches a text query.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        input_schema=SearchTasksArgs,
        handler=search_tasks_tool,
    ),
    "save_memory": RegisteredTool(
        name="save_memory",
        description=(
            "Save or update a persistent long-term user preference or fact as a key-value pair "
            "(for example, key='meeting_preference', value='afternoon')."
        ),
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Short snake_case key identifying the preference or fact.",
                },
                "value": {"type": "string", "description": "The preference or fact value to remember."},
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
        input_schema=SaveMemoryArgs,
        handler=save_memory_tool,
    ),
    "retrieve_memory": RegisteredTool(
        name="retrieve_memory",
        description=(
            "Retrieve long-term user memories or preferences. Pass a specific key or omit key "
            "to inspect all stored memories."
        ),
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": ["string", "null"],
                    "description": "Optional key to look up. Omit to return all saved memories.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        input_schema=RetrieveMemoryArgs,
        handler=retrieve_memory_tool,
    ),
    "create_reminder": RegisteredTool(
        name="create_reminder",
        description="Create a persistent reminder for the user at a specified date/time.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "What to remind the user about."},
                "remind_at": {
                    "type": "string",
                    "description": "ISO datetime or readable schedule string (e.g. '2026-11-27T09:00:00').",
                },
                "task_id": {
                    "type": ["integer", "null"],
                    "description": "Optional linked LifeDesk task ID.",
                },
            },
            "required": ["title", "remind_at"],
            "additionalProperties": False,
        },
        input_schema=CreateReminderArgs,
        handler=create_reminder_tool,
    ),
    "list_reminders": RegisteredTool(
        name="list_reminders",
        description="List stored reminders for the user, optionally filtered by status.",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": ["string", "null"],
                    "enum": ["pending", "triggered", "dismissed", None],
                    "description": "Optional reminder status filter.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        input_schema=ListRemindersArgs,
        handler=list_reminders_tool,
    ),
    "get_user_preferences": RegisteredTool(
        name="get_user_preferences",
        description="Retrieve the user's configured timezone, profile name, and saved preferences.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        input_schema=GetUserPreferencesArgs,
        handler=get_user_preferences_tool,
    ),
    "request_user_approval": RegisteredTool(
        name="request_user_approval",
        description=(
            "Stage a custom internal confirmation request only when no built-in Gmail or Calendar "
            "approval-gated tool applies (do NOT call this for gmail_send_email or calendar_*)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "description": "Short action identifier."},
                "provider": {"type": ["string", "null"], "description": "Target provider (e.g. 'internal')."},
                "tool_name": {"type": "string", "description": "Target tool name."},
                "summary": {
                    "type": "string",
                    "description": "Clear human-readable summary of the proposed action.",
                },
                "action_payload": {
                    "type": "object",
                    "description": "Exact JSON payload awaiting user approval.",
                },
            },
            "required": ["action_type", "tool_name", "summary", "action_payload"],
            "additionalProperties": False,
        },
        input_schema=RequestUserApprovalArgs,
        handler=request_user_approval_tool,
    ),
}


def get_openai_tools() -> list[dict[str, Any]]:
    """Return OpenAI tool definitions for all registered native tools."""
    return [tool.to_openai_tool() for tool in TOOL_REGISTRY.values()]


def execute_registered_tool(
    db: Session,
    tool_name: str,
    raw_arguments: Any,
    *,
    user_id: int = 1,
    conversation_id: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Validate native tool name and arguments, execute handler, and return (success, payload)."""
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        logger.warning("tool_rejected name=%s reason=unregistered", tool_name)
        return False, {
            "status": "error",
            "error": f"Tool '{tool_name}' is not registered and cannot be executed.",
        }

    if not isinstance(raw_arguments, dict):
        logger.warning("tool_rejected name=%s reason=non_object_args", tool_name)
        return False, {
            "status": "error",
            "error": f"Arguments for '{tool_name}' must be a JSON object.",
        }

    try:
        validated_args = tool.input_schema.model_validate(raw_arguments)
    except ValidationError as exc:
        logger.warning("tool_rejected name=%s reason=validation_error", tool_name)
        return False, {
            "status": "error",
            "error": f"Invalid arguments for '{tool_name}': {exc.errors()}",
        }

    try:
        sig = inspect.signature(tool.handler)
        kwargs: dict[str, Any] = {}
        if "user_id" in sig.parameters:
            kwargs["user_id"] = user_id
        if "conversation_id" in sig.parameters:
            kwargs["conversation_id"] = conversation_id
        result = tool.handler(db, validated_args, **kwargs)
    except Exception as exc:
        logger.exception("tool_failed name=%s", tool_name)
        return False, {
            "status": "error",
            "error": f"Execution failed for '{tool_name}': {exc}",
        }

    succeeded = result.get("status") != "error"
    logger.info("tool_executed name=%s success=%s", tool_name, succeeded)
    return succeeded, result
