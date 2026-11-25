"""Unit tests for LifeDeskAgent multi-tool loop, safety guards, and all user scenarios."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.agent.agent import AgentExecutionError, LifeDeskAgent
from app.agent.llm_provider import LLMProvider
from app.config import Settings
from app.database.repositories import ConversationRepository, TaskRepository


class MockChatCompletions:
    """Scripted sequence of OpenAI ChatCompletion responses."""

    def __init__(self, messages: list[Any]) -> None:
        self._messages = list(messages)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        msg = self._messages.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _make_tool_call(call_id: str, name: str, args: dict[str, Any] | str) -> Any:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(
            name=name,
            arguments=args if isinstance(args, str) else json.dumps(args),
        ),
    )


def _make_agent(
    responses: list[Any],
    *,
    provider_name: str = "groq",
    max_tool_iterations: int = 5,
) -> tuple[LifeDeskAgent, MockChatCompletions]:
    completions = MockChatCompletions(responses)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    settings = Settings(
        llm_provider=provider_name,  # type: ignore[arg-type]
        groq_api_key="test-key",
        openrouter_api_key="test-key",
        max_tool_iterations=max_tool_iterations,
    )
    provider = LLMProvider(settings, client=client)
    return LifeDeskAgent(settings=settings, provider=provider), completions


def test_scenarios_create_list_complete_and_memory_across_providers(
    db_session: Session,
) -> None:
    # Scenario 1 & 4: Parallel tool calls (create task + save memory in one turn) on Groq.
    agent_groq, _ = _make_agent(
        [
            SimpleNamespace(
                content=None,
                tool_calls=[
                    _make_tool_call(
                        "call_1",
                        "create_task",
                        {"title": "Complete DSA assignment", "due_date": "2026-11-30"},
                    ),
                    _make_tool_call(
                        "call_2",
                        "save_memory",
                        {"key": "meeting_preference", "value": "afternoon"},
                    ),
                ],
            ),
            SimpleNamespace(
                content="Created task #1 'Complete DSA assignment' and saved your afternoon meeting preference.",
                tool_calls=None,
            ),
        ],
        provider_name="groq",
    )

    res1 = agent_groq.run(
        db_session,
        user_message="Create a task called Complete DSA assignment and remember I prefer afternoon meetings.",
    )
    assert res1.provider == "groq"
    assert len(res1.tool_calls) == 2
    assert all(tc.success for tc in res1.tool_calls)

    # Scenario 2 & 3 & 6: Switch to OpenRouter, sequentially list tasks then complete task 1.
    agent_or, or_calls = _make_agent(
        [
            SimpleNamespace(
                content=None,
                tool_calls=[_make_tool_call("call_3", "list_tasks", {})],
            ),
            SimpleNamespace(
                content=None,
                tool_calls=[_make_tool_call("call_4", "complete_task", {"task_id": 1})],
            ),
            SimpleNamespace(
                content="Task 1 ('Complete DSA assignment') is now marked completed.",
                tool_calls=None,
            ),
        ],
        provider_name="openrouter",
    )

    res2 = agent_or.run(
        db_session,
        user_message="List my tasks and mark task 1 as completed.",
        conversation_id=res1.conversation_id,
    )
    assert res2.provider == "openrouter"
    assert res2.iterations_used == 3
    assert [tc.tool_name for tc in res2.tool_calls] == ["list_tasks", "complete_task"]
    assert TaskRepository(db_session).get_by_id(1).status == "completed"  # type: ignore[union-attr]
    # Verify persisted history was sent on the follow-up turn.
    assert any(m["role"] == "user" for m in or_calls.calls[0]["messages"])

    # Verify conversation messages persisted in SQLite.
    messages = ConversationRepository(db_session).list_messages(res1.conversation_id)
    assert len(messages) >= 5


def test_normal_question_and_ambiguous_request_without_tools(db_session: Session) -> None:
    agent, _ = _make_agent(
        [
            SimpleNamespace(content="Python is a high-level programming language.", tool_calls=None),
            SimpleNamespace(content="What would you like the task to be titled?", tool_calls=None),
        ]
    )

    res_normal = agent.run(db_session, user_message="What is Python?")
    assert res_normal.tool_calls == []
    assert res_normal.iterations_used == 1

    res_ambiguous = agent.run(db_session, user_message="Add a task for me")
    assert res_ambiguous.tool_calls == []
    assert "titled" in res_ambiguous.reply.lower()


def test_unknown_tool_and_malformed_json_are_safely_rejected(db_session: Session) -> None:
    agent, _ = _make_agent(
        [
            SimpleNamespace(
                content=None,
                tool_calls=[
                    _make_tool_call("c1", "execute_python", {"code": "__import__('os')"}),
                    _make_tool_call("c2", "create_task", "{not valid json"),
                ],
            ),
            SimpleNamespace(
                content="I could not execute that request due to invalid tool calls.",
                tool_calls=None,
            ),
        ]
    )

    res = agent.run(db_session, user_message="Run python")
    assert len(res.tool_calls) == 2
    assert all(not tc.success for tc in res.tool_calls)
    assert TaskRepository(db_session).list_all() == []


def test_max_iterations_prevents_infinite_loop(db_session: Session) -> None:
    loop_msg = SimpleNamespace(
        content=None,
        tool_calls=[_make_tool_call("c_loop", "list_tasks", {})],
    )
    agent, _ = _make_agent([loop_msg, loop_msg, loop_msg], max_tool_iterations=2)

    with pytest.raises(AgentExecutionError) as exc_info:
        agent.run(db_session, user_message="Keep looping")
    assert "maximum limit of 2" in str(exc_info.value)
