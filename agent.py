"""Gemini Interactions API agent loop and safe tool orchestration."""

import json
from typing import Any

from google import genai
from google.genai import errors as genai_errors

from config import Settings
from schemas import ChatResponse, ToolExecutionRecord
from tools import execute_registered_tool, get_tool_declarations

SYSTEM_INSTRUCTION = (
    "You are MiniTask Agent, the task-management assistant for LifeDesk AI. "
    "When the user asks to create, add, remember, or schedule a task, call the "
    "`create_task` tool with a clear title and an optional due_date if provided. "
    "If the user is just chatting or asking a question that does not require creating "
    "a task, respond directly without calling any tools. "
    "Never claim a task was created unless you receive a tool result confirming "
    "status='created' with a task ID. If a tool returns an error, explain the issue "
    "honestly and ask the user for clarification."
)


class AgentConfigurationError(Exception):
    """Raised when required Gemini configuration (such as GEMINI_API_KEY) is missing."""


class AgentExecutionError(Exception):
    """Raised when Gemini API calls or tool-loop execution fail."""


class MiniTaskAgent:
    """Coordinates Gemini function calling and validated backend tool execution."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client

    def _get_client(self) -> Any:
        """Return an initialized Google GenAI client or raise if API key is missing."""
        if self._client is not None:
            return self._client

        if not self.settings.gemini_api_key:
            raise AgentConfigurationError(
                "GEMINI_API_KEY is not configured. Add it to your .env file or environment."
            )

        self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def _call_interactions(
        self,
        client: Any,
        *,
        interaction_input: Any,
        tools: list[dict[str, Any]],
        previous_interaction_id: str | None = None,
    ) -> Any:
        """Invoke Gemini's Interactions API with consistent error wrapping."""
        kwargs: dict[str, Any] = {
            "model": self.settings.gemini_model,
            "system_instruction": SYSTEM_INSTRUCTION,
            "input": interaction_input,
            "tools": tools,
        }
        if previous_interaction_id is not None:
            kwargs["previous_interaction_id"] = previous_interaction_id

        try:
            return client.interactions.create(**kwargs)
        except genai_errors.APIError as exc:
            raise AgentExecutionError(f"Gemini API error: {exc}") from exc
        except Exception as exc:
            raise AgentExecutionError(f"Unexpected error calling Gemini API: {exc}") from exc

    @staticmethod
    def _extract_reply_text(interaction: Any) -> str:
        """Extract the final assistant text from an Interaction response."""
        output_text = getattr(interaction, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        text_chunks: list[str] = []
        for step in getattr(interaction, "steps", None) or []:
            if getattr(step, "type", None) == "model_output":
                for block in getattr(step, "content", None) or []:
                    if getattr(block, "type", None) == "text":
                        text = getattr(block, "text", None)
                        if isinstance(text, str) and text.strip():
                            text_chunks.append(text.strip())

        return "\n".join(text_chunks).strip()

    def run(self, user_message: str) -> ChatResponse:
        """Process one user message through Gemini with bounded tool execution."""
        client = self._get_client()
        tool_declarations = get_tool_declarations()
        tool_records: list[ToolExecutionRecord] = []

        interaction = self._call_interactions(
            client,
            interaction_input=user_message,
            tools=tool_declarations,
        )

        # Bound tool execution rounds to prevent infinite model-tool loops.
        for _ in range(self.settings.max_tool_iterations):
            steps = getattr(interaction, "steps", None) or []
            function_calls = [s for s in steps if getattr(s, "type", None) == "function_call"]

            if not function_calls:
                reply = self._extract_reply_text(interaction)
                if not reply:
                    raise AgentExecutionError("Gemini returned an empty response.")
                return ChatResponse(
                    reply=reply,
                    interaction_id=getattr(interaction, "id", None),
                    tool_calls=tool_records,
                )

            function_results: list[dict[str, Any]] = []
            for fc_step in function_calls:
                call_id = getattr(fc_step, "id", "") or ""
                tool_name = getattr(fc_step, "name", "") or ""
                raw_arguments = getattr(fc_step, "arguments", None)

                success, result = execute_registered_tool(tool_name, raw_arguments)
                tool_records.append(
                    ToolExecutionRecord(
                        call_id=call_id,
                        tool_name=tool_name,
                        arguments=raw_arguments if isinstance(raw_arguments, dict) else {},
                        success=success,
                        result=result,
                    )
                )
                function_results.append(
                    {
                        "type": "function_result",
                        "name": tool_name,
                        "call_id": call_id,
                        "result": [{"type": "text", "text": json.dumps(result)}],
                    }
                )

            interaction = self._call_interactions(
                client,
                interaction_input=function_results,
                tools=tool_declarations,
                previous_interaction_id=getattr(interaction, "id", None),
            )

        final_steps = getattr(interaction, "steps", None) or []
        remaining_calls = [s for s in final_steps if getattr(s, "type", None) == "function_call"]
        if remaining_calls:
            raise AgentExecutionError(
                f"Exceeded maximum tool execution iterations ({self.settings.max_tool_iterations})."
            )

        reply = self._extract_reply_text(interaction)
        if not reply:
            raise AgentExecutionError("Gemini returned an empty response after tool execution.")

        return ChatResponse(
            reply=reply,
            interaction_id=getattr(interaction, "id", None),
            tool_calls=tool_records,
        )
