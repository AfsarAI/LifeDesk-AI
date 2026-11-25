"""Multi-tool agent execution loop backed by persistent SQLite conversations."""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agent.llm_provider import LLMProvider, LLMProviderError
from app.agent.tool_registry import execute_registered_tool, get_openai_tools
from app.config import Settings
from app.database.repositories import ConversationRepository
from app.schemas.chat import ChatResponse, ToolExecutionRecord

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are LifeDesk AI, a reliable personal productivity and task assistant.\n\n"
    "Available capabilities:\n"
    "- Manage tasks with `create_task`, `list_tasks`, `update_task`, `complete_task`, and `search_tasks`.\n"
    "- Store and recall user preferences or facts with `save_memory` and `retrieve_memory`.\n\n"
    "Rules you MUST follow:\n"
    "1. Only call tools when needed. For general questions or greetings, answer directly without tools.\n"
    "2. If a user asks to create, update, or complete a task but the request is ambiguous "
    "(for example missing a task title or unclear which task to update), ask a short clarifying question "
    "instead of inventing details.\n"
    "3. When the user states a persistent preference (such as preferred meeting times), call `save_memory` "
    "with a concise snake_case key.\n"
    "4. When the user asks a question that depends on preferences or stored facts (for example scheduling "
    "advice or 'what do you remember'), call `retrieve_memory` before answering.\n"
    "5. Never claim a task or memory action succeeded unless the tool returned a successful result "
    "('created', 'updated', 'completed', or 'ok'). If a tool returns an error, report it honestly."
)

HISTORY_LIMIT = 20


class AgentExecutionError(Exception):
    """Raised when the agent exceeds iteration limits or cannot produce a valid reply."""


class ConversationNotFoundError(Exception):
    """Raised when a requested conversation_id does not exist."""


class LifeDeskAgent:
    """Orchestrates multi-turn, multi-tool reasoning with bounded iterations."""

    def __init__(self, settings: Settings, provider: LLMProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider or LLMProvider(settings)

    @staticmethod
    def _parse_tool_arguments(raw_args: Any) -> tuple[bool, dict[str, Any], str | None]:
        """Parse OpenAI tool_call arguments safely into a dictionary."""
        if isinstance(raw_args, dict):
            return True, raw_args, None
        if not isinstance(raw_args, str):
            return False, {}, "Tool arguments must be a JSON object string."
        text = raw_args.strip()
        if not text:
            return True, {}, None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return False, {}, f"Malformed JSON tool arguments: {exc}"
        if not isinstance(parsed, dict):
            return False, {}, "Decoded tool arguments must be a JSON object."
        return True, parsed, None

    @staticmethod
    def _build_llm_messages(db: Session, conversation_id: int) -> list[dict[str, Any]]:
        """Convert recent persisted user/assistant messages into LLM chat history."""
        repo = ConversationRepository(db)
        recent = repo.list_messages(conversation_id)[-HISTORY_LIMIT:]
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in recent:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})
        return messages

    def run(
        self,
        db: Session,
        *,
        user_message: str,
        conversation_id: int | None = None,
    ) -> ChatResponse:
        """Process one user message through the bounded multi-tool agent loop."""
        conv_repo = ConversationRepository(db)

        if conversation_id is not None:
            conversation = conv_repo.get_by_id(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError(f"Conversation {conversation_id} was not found.")
        else:
            title = user_message[:60].strip() or "New Chat"
            conversation = conv_repo.create(title=title)

        conv_repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )

        llm_messages = self._build_llm_messages(db, conversation.id)
        tools = get_openai_tools()
        tool_records: list[ToolExecutionRecord] = []

        for iteration in range(1, self.settings.max_tool_iterations + 1):
            assistant_msg = self.provider.create_chat_completion(
                messages=llm_messages,
                tools=tools,
            )

            raw_tool_calls = getattr(assistant_msg, "tool_calls", None) or []
            if not raw_tool_calls:
                reply_text = (getattr(assistant_msg, "content", None) or "").strip()
                if not reply_text:
                    raise LLMProviderError(
                        "The LLM provider returned an empty response.",
                        status_code=502,
                        error_code="malformed_response",
                    )

                conv_repo.add_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=reply_text,
                    tool_metadata=(
                        json.dumps([r.model_dump(mode="json") for r in tool_records])
                        if tool_records
                        else None
                    ),
                )

                return ChatResponse(
                    conversation_id=conversation.id,
                    reply=reply_text,
                    provider=self.provider.config.provider,
                    model=self.provider.config.model,
                    iterations_used=iteration,
                    tool_calls=tool_records,
                )

            # Append the assistant tool-calling turn before appending role="tool" results.
            serialized_tool_calls: list[dict[str, Any]] = []
            for tc in raw_tool_calls:
                fn = getattr(tc, "function", None)
                tc_name = getattr(fn, "name", "") or ""
                tc_args_raw = getattr(fn, "arguments", "{}")
                serialized_tool_calls.append(
                    {
                        "id": getattr(tc, "id", ""),
                        "type": "function",
                        "function": {
                            "name": tc_name,
                            "arguments": (
                                tc_args_raw
                                if isinstance(tc_args_raw, str)
                                else json.dumps(tc_args_raw)
                            ),
                        },
                    }
                )

            llm_messages.append(
                {
                    "role": "assistant",
                    "content": getattr(assistant_msg, "content", None) or "",
                    "tool_calls": serialized_tool_calls,
                }
            )

            for tc in raw_tool_calls:
                call_id = getattr(tc, "id", "") or ""
                fn = getattr(tc, "function", None)
                tool_name = getattr(fn, "name", "") or ""
                raw_args = getattr(fn, "arguments", "{}")

                ok_json, parsed_args, parse_error = self._parse_tool_arguments(raw_args)
                if not ok_json:
                    success = False
                    result: dict[str, Any] = {
                        "status": "error",
                        "error": parse_error or "Invalid tool argument JSON.",
                    }
                    logger.warning("tool_rejected name=%s reason=malformed_json", tool_name)
                else:
                    success, result = execute_registered_tool(db, tool_name, parsed_args)

                record = ToolExecutionRecord(
                    call_id=call_id,
                    tool_name=tool_name,
                    arguments=parsed_args,
                    success=success,
                    result=result,
                )
                tool_records.append(record)

                conv_repo.add_message(
                    conversation_id=conversation.id,
                    role="tool",
                    content=json.dumps(result),
                    tool_metadata=json.dumps(record.model_dump(mode="json")),
                )

                llm_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result),
                    }
                )

        raise AgentExecutionError(
            f"Agent reached the maximum limit of {self.settings.max_tool_iterations} "
            "iterations without producing a final response."
        )
