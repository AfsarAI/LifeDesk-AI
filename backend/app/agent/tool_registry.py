"""Explicitly registered tool definitions, JSON schemas, and safe dispatcher."""

from dataclasses import dataclass
import logging
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.schemas.memory import RetrieveMemoryArgs, SaveMemoryArgs
from app.schemas.task import (
    CompleteTaskArgs,
    CreateTaskArgs,
    ListTasksArgs,
    SearchTasksArgs,
    UpdateTaskArgs,
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
    """Definition and handler for an explicitly allowed agent tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    input_schema: type[BaseModel]
    handler: Callable[[Session, Any], dict[str, Any]]

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


# Security boundary: only tools registered here may be executed by the agent.
TOOL_REGISTRY: dict[str, RegisteredTool] = {
    "create_task": RegisteredTool(
        name="create_task",
        description=(
            "Create a new task in the database. Use only when the user clearly asks to "
            "create, add, or schedule a task and provides a task title."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Concise title of the task.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional due date or deadline (e.g., '2026-11-30' or 'tomorrow').",
                },
                "description": {
                    "type": "string",
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
        description="List all stored tasks, optionally filtered by status ('pending' or 'completed').",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "completed"],
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
                "task_id": {
                    "type": "integer",
                    "description": "Numeric ID of the task to update.",
                },
                "title": {
                    "type": "string",
                    "description": "Updated task title.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Updated due date.",
                },
                "description": {
                    "type": "string",
                    "description": "Updated task description.",
                },
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
        description="Search tasks whose title or description matches a text query.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword or phrase.",
                },
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
                "value": {
                    "type": "string",
                    "description": "The preference or fact value to remember.",
                },
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
                    "type": "string",
                    "description": "Optional key to look up. Omit to return all saved memories.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        input_schema=RetrieveMemoryArgs,
        handler=retrieve_memory_tool,
    ),
}


def get_openai_tools() -> list[dict[str, Any]]:
    """Return OpenAI tool definitions for all registered tools."""
    return [tool.to_openai_tool() for tool in TOOL_REGISTRY.values()]


def execute_registered_tool(
    db: Session,
    tool_name: str,
    raw_arguments: Any,
) -> tuple[bool, dict[str, Any]]:
    """Validate tool name and arguments, execute the handler, and return (success, payload)."""
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
        result = tool.handler(db, validated_args)
    except Exception as exc:
        logger.exception("tool_failed name=%s", tool_name)
        return False, {
            "status": "error",
            "error": f"Execution failed for '{tool_name}': {exc}",
        }

    succeeded = result.get("status") != "error"
    logger.info("tool_executed name=%s success=%s", tool_name, succeeded)
    return succeeded, result
