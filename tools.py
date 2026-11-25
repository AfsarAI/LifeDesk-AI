"""Explicitly registered tools and temporary in-memory task storage."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
import uuid

from pydantic import BaseModel, ValidationError

from schemas import CreateTaskArgs, Task

# Temporary in-memory task storage for Day 1.
_tasks_store: list[Task] = []


def list_tasks() -> list[Task]:
    """Return a shallow copy of all tasks currently stored in memory."""
    return list(_tasks_store)


def clear_tasks() -> None:
    """Clear the in-memory task store (used in automated tests)."""
    _tasks_store.clear()


def create_task(args: CreateTaskArgs) -> dict[str, Any]:
    """Create a task with a generated ID and store it in memory."""
    task = Task(
        id=f"task_{uuid.uuid4().hex[:8]}",
        title=args.title,
        due_date=args.due_date,
        created_at=datetime.now(timezone.utc),
    )
    _tasks_store.append(task)
    return {
        "status": "created",
        "task": task.model_dump(mode="json"),
    }


CREATE_TASK_DECLARATION: dict[str, Any] = {
    "type": "function",
    "name": "create_task",
    "description": (
        "Creates a new task and saves it to the user's task list. "
        "Use this only when the user asks to create, add, remember, or schedule a task."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Concise title of the task to create.",
            },
            "due_date": {
                "type": "string",
                "description": (
                    "Optional due date or deadline mentioned by the user "
                    "(e.g., '2026-11-30' or 'tomorrow')."
                ),
            },
        },
        "required": ["title"],
    },
}


@dataclass(frozen=True)
class RegisteredTool:
    """Metadata and handler for an explicitly allowed backend tool."""

    name: str
    declaration: dict[str, Any]
    input_schema: type[BaseModel]
    handler: Callable[[Any], dict[str, Any]]


# Security boundary: only tools listed here can ever be invoked by the agent.
TOOL_REGISTRY: dict[str, RegisteredTool] = {
    "create_task": RegisteredTool(
        name="create_task",
        declaration=CREATE_TASK_DECLARATION,
        input_schema=CreateTaskArgs,
        handler=create_task,
    ),
}


def get_tool_declarations() -> list[dict[str, Any]]:
    """Return Gemini function declarations for all registered tools."""
    return [tool.declaration for tool in TOOL_REGISTRY.values()]


def execute_registered_tool(
    tool_name: str,
    raw_arguments: Any,
) -> tuple[bool, dict[str, Any]]:
    """Validate tool name and arguments, then execute the registered Python function."""
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return False, {
            "status": "error",
            "error": f"Tool '{tool_name}' is not registered and cannot be executed.",
        }

    if not isinstance(raw_arguments, dict):
        return False, {
            "status": "error",
            "error": f"Arguments for '{tool_name}' must be a JSON object.",
        }

    try:
        validated_args = tool.input_schema.model_validate(raw_arguments)
    except ValidationError as exc:
        return False, {
            "status": "error",
            "error": f"Invalid arguments for '{tool_name}': {exc.errors()}",
        }

    try:
        result = tool.handler(validated_args)
    except Exception as exc:
        return False, {
            "status": "error",
            "error": f"Execution failed for '{tool_name}': {exc}",
        }

    return True, result
