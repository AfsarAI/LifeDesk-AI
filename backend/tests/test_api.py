"""Integration tests for all FastAPI /api/* endpoints."""

import json
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from app.agent.agent import LifeDeskAgent
from app.agent.llm_provider import LLMProvider
from app.api.routes.chat import get_agent
from app.config import Settings


def test_health_endpoint_hides_secrets(api_client: TestClient) -> None:
    resp = api_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert "api_key" not in json.dumps(data)


def test_tasks_crud_endpoints(api_client: TestClient) -> None:
    create_resp = api_client.post(
        "/api/tasks",
        json={"title": "Write tests", "description": "Cover all routes", "due_date": "2026-12-01"},
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    list_resp = api_client.get("/api/tasks")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 1
    assert list_resp.json()["pending_count"] == 1

    patch_resp = api_client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "completed"

    search_resp = api_client.get("/api/tasks?q=tests")
    assert search_resp.status_code == 200
    assert search_resp.json()["count"] == 1

    del_resp = api_client.delete(f"/api/tasks/{task_id}")
    assert del_resp.status_code == 204
    assert api_client.get("/api/tasks").json()["count"] == 0


def test_memories_crud_endpoints(api_client: TestClient) -> None:
    post_resp = api_client.post(
        "/api/memories",
        json={"key": "Meeting Preference", "value": "afternoon"},
    )
    assert post_resp.status_code == 201
    mem_id = post_resp.json()["id"]
    assert post_resp.json()["key"] == "meeting_preference"

    # Upsert same normalized key updates rather than duplicating.
    upsert_resp = api_client.post(
        "/api/memories",
        json={"key": "meeting_preference", "value": "late afternoon"},
    )
    assert upsert_resp.status_code == 201
    assert api_client.get("/api/memories").json()["count"] == 1

    patch_resp = api_client.patch(f"/api/memories/{mem_id}", json={"value": "3 PM"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["value"] == "3 PM"

    del_resp = api_client.delete(f"/api/memories/{mem_id}")
    assert del_resp.status_code == 204
    assert api_client.get("/api/memories").json()["count"] == 0


def test_chat_and_conversations_endpoints(api_client: TestClient) -> None:
    scripted_messages = [
        SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    id="call_api_1",
                    type="function",
                    function=SimpleNamespace(
                        name="create_task",
                        arguments=json.dumps({"title": "Prepare demo"}),
                    ),
                )
            ],
        ),
        SimpleNamespace(
            content="I created the task 'Prepare demo' for you.",
            tool_calls=None,
        ),
    ]
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kw: SimpleNamespace(
                choices=[SimpleNamespace(message=scripted_messages.pop(0))]
            ))
        )
    )
    settings = Settings(llm_provider="groq", groq_api_key="test-key")
    agent = LifeDeskAgent(settings=settings, provider=LLMProvider(settings, client=fake_client))
    api_client.app.dependency_overrides[get_agent] = lambda: agent  # type: ignore[attr-defined]

    try:
        chat_resp = api_client.post("/api/chat", json={"message": "Create a task Prepare demo"})
        assert chat_resp.status_code == 200
        body = chat_resp.json()
        conv_id = body["conversation_id"]
        assert body["tool_calls"][0]["tool_name"] == "create_task"

        convs_resp = api_client.get("/api/conversations")
        assert convs_resp.status_code == 200
        assert convs_resp.json()["count"] == 1

        msgs_resp = api_client.get(f"/api/conversations/{conv_id}/messages")
        assert msgs_resp.status_code == 200
        assert len(msgs_resp.json()["messages"]) == 3
    finally:
        api_client.app.dependency_overrides.pop(get_agent, None)  # type: ignore[attr-defined]
