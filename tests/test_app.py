"""Automated tests for MiniTask Agent routes, tool validation, and agent loop."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent import AgentConfigurationError, MiniTaskAgent
from config import Settings
from main import app, get_agent
from tools import clear_tasks, execute_registered_tool, list_tasks


@pytest.fixture(autouse=True)
def reset_task_store() -> None:
    """Ensure each test starts with an empty in-memory task store."""
    clear_tasks()


class FakeInteractionsResource:
    """Simulates client.interactions.create responses in sequence."""

    def __init__(self, responses: list[Any], error: Exception | None = None) -> None:
        self._responses = list(responses)
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._responses.pop(0)


class FakeGenAIClient:
    """Minimal fake matching the google.genai.Client interface used by MiniTaskAgent."""

    def __init__(self, responses: list[Any], error: Exception | None = None) -> None:
        self.interactions = FakeInteractionsResource(responses, error=error)


def test_get_tasks_initially_empty() -> None:
    client = TestClient(app)
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == {"tasks": [], "count": 0}


def test_chat_creates_task_via_tool_call_and_persists_in_memory() -> None:
    fake_client = FakeGenAIClient(
        responses=[
            SimpleNamespace(
                id="inter_1",
                output_text=None,
                steps=[
                    SimpleNamespace(
                        type="function_call",
                        id="call_abc123",
                        name="create_task",
                        arguments={"title": "Buy groceries", "due_date": "2026-11-26"},
                    )
                ],
            ),
            SimpleNamespace(
                id="inter_2",
                output_text="I have created your task 'Buy groceries' due on 2026-11-26.",
                steps=[
                    SimpleNamespace(
                        type="model_output",
                        content=[
                            SimpleNamespace(
                                type="text",
                                text="I have created your task 'Buy groceries' due on 2026-11-26.",
                            )
                        ],
                    )
                ],
            ),
        ]
    )
    settings = Settings(gemini_api_key="test-key", gemini_model="gemini-4-hydrogen", max_tool_iterations=5)
    app.dependency_overrides[get_agent] = lambda: MiniTaskAgent(settings=settings, client=fake_client)

    try:
        client = TestClient(app)
        chat_response = client.post(
            "/chat",
            json={"message": "Add a task to buy groceries by 2026-11-26"},
        )
        assert chat_response.status_code == 200
        body = chat_response.json()
        assert body["interaction_id"] == "inter_2"
        assert "Buy groceries" in body["reply"]
        assert len(body["tool_calls"]) == 1
        assert body["tool_calls"][0]["tool_name"] == "create_task"
        assert body["tool_calls"][0]["success"] is True

        # Verify GET /tasks returns the newly stored task.
        tasks_response = client.get("/tasks")
        assert tasks_response.status_code == 200
        tasks_body = tasks_response.json()
        assert tasks_body["count"] == 1
        assert tasks_body["tasks"][0]["title"] == "Buy groceries"
        assert tasks_body["tasks"][0]["due_date"] == "2026-11-26"
        assert tasks_body["tasks"][0]["id"].startswith("task_")

        # Verify second Gemini call included previous_interaction_id, tools, and function_result.
        second_call = fake_client.interactions.calls[1]
        assert second_call["previous_interaction_id"] == "inter_1"
        assert second_call["tools"][0]["name"] == "create_task"
        assert second_call["input"][0]["type"] == "function_result"
        assert second_call["input"][0]["call_id"] == "call_abc123"
    finally:
        app.dependency_overrides.clear()


def test_tool_registry_rejects_unregistered_tools_and_invalid_args() -> None:
    ok_unknown, res_unknown = execute_registered_tool("exec_python", {"code": "print(1)"})
    assert ok_unknown is False
    assert "not registered" in res_unknown["error"]

    ok_blank, res_blank = execute_registered_tool("create_task", {"title": "   "})
    assert ok_blank is False
    assert "Invalid arguments" in res_blank["error"]

    ok_extra, res_extra = execute_registered_tool(
        "create_task",
        {"title": "Valid", "unexpected": "bad"},
    )
    assert ok_extra is False
    assert "Invalid arguments" in res_extra["error"]
    assert list_tasks() == []


def test_agent_enforces_max_tool_iterations() -> None:
    looping_step = SimpleNamespace(
        id="inter_loop",
        output_text=None,
        steps=[
            SimpleNamespace(
                type="function_call",
                id="call_loop",
                name="create_task",
                arguments={"title": "Repeated task"},
            )
        ],
    )
    fake_client = FakeGenAIClient(responses=[looping_step, looping_step, looping_step])
    settings = Settings(gemini_api_key="test-key", max_tool_iterations=2)
    app.dependency_overrides[get_agent] = lambda: MiniTaskAgent(settings=settings, client=fake_client)

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "Create a task"})
        assert response.status_code == 502
        assert "maximum tool execution iterations" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_chat_returns_503_when_api_key_missing() -> None:
    settings = Settings(gemini_api_key=None)
    app.dependency_overrides[get_agent] = lambda: MiniTaskAgent(settings=settings)

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 503
        assert "GEMINI_API_KEY" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_chat_handles_upstream_api_failure() -> None:
    fake_client = FakeGenAIClient(responses=[], error=RuntimeError("network timeout"))
    settings = Settings(gemini_api_key="test-key")
    app.dependency_overrides[get_agent] = lambda: MiniTaskAgent(settings=settings, client=fake_client)

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "Create task X"})
        assert response.status_code == 502
        assert "network timeout" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_chat_sends_validation_error_back_to_gemini_without_creating_task() -> None:
    fake_client = FakeGenAIClient(
        responses=[
            SimpleNamespace(
                id="inter_bad_args",
                output_text=None,
                steps=[
                    SimpleNamespace(
                        type="function_call",
                        id="call_bad_1",
                        name="create_task",
                        arguments={"title": ""},
                    )
                ],
            ),
            SimpleNamespace(
                id="inter_clarify",
                output_text="Could you tell me the title of the task you want to create?",
                steps=[],
            ),
        ]
    )
    settings = Settings(gemini_api_key="test-key", max_tool_iterations=5)
    app.dependency_overrides[get_agent] = lambda: MiniTaskAgent(settings=settings, client=fake_client)

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "Create a blank task"})
        assert response.status_code == 200
        body = response.json()
        assert len(body["tool_calls"]) == 1
        assert body["tool_calls"][0]["success"] is False
        assert "Invalid arguments" in body["tool_calls"][0]["result"]["error"]
        assert client.get("/tasks").json()["count"] == 0
    finally:
        app.dependency_overrides.clear()
