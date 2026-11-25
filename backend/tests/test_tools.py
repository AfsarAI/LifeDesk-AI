"""Unit tests for all 7 tools, validation, and SQLite persistence across restarts."""

from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.agent.tool_registry import execute_registered_tool
from app.database.database import create_db_engine, init_db


def test_task_tools_full_lifecycle(db_session: Session) -> None:
    ok, created = execute_registered_tool(
        db_session,
        "create_task",
        {"title": "Complete DSA assignment", "due_date": "2026-11-30", "description": "Trees & graphs"},
    )
    assert ok is True
    assert created["status"] == "created"
    task_id = created["task"]["id"]

    ok_list, listed = execute_registered_tool(db_session, "list_tasks", {})
    assert ok_list is True
    assert listed["count"] == 1

    ok_search, found = execute_registered_tool(db_session, "search_tasks", {"query": "DSA"})
    assert ok_search is True
    assert found["count"] == 1

    ok_upd, updated = execute_registered_tool(
        db_session,
        "update_task",
        {"task_id": task_id, "title": "Complete DSA assignment (updated)"},
    )
    assert ok_upd is True
    assert updated["task"]["title"] == "Complete DSA assignment (updated)"

    ok_done, completed = execute_registered_tool(
        db_session,
        "complete_task",
        {"task_id": task_id},
    )
    assert ok_done is True
    assert completed["task"]["status"] == "completed"


def test_missing_task_id_and_invalid_arguments(db_session: Session) -> None:
    ok_missing, res_missing = execute_registered_tool(
        db_session,
        "complete_task",
        {"task_id": 999},
    )
    assert ok_missing is False
    assert "not found" in res_missing["error"]

    ok_unknown, res_unknown = execute_registered_tool(
        db_session,
        "run_sql",
        {"query": "DROP TABLE tasks"},
    )
    assert ok_unknown is False
    assert "not registered" in res_unknown["error"]

    ok_blank, res_blank = execute_registered_tool(
        db_session,
        "create_task",
        {"title": "   "},
    )
    assert ok_blank is False
    assert "Invalid arguments" in res_blank["error"]


def test_memory_upsert_prevents_duplicates_and_persists_across_restarts(
    sqlite_db_path: Path,
) -> None:
    engine1 = create_db_engine(f"sqlite:///{sqlite_db_path}")
    init_db(engine1)
    session_factory1 = sessionmaker(bind=engine1, autocommit=False, autoflush=False, class_=Session)

    with session_factory1() as db1:
        ok1, res1 = execute_registered_tool(
            db1, "save_memory", {"key": "Meeting Preference", "value": "morning"}
        )
        assert ok1 is True
        assert res1["status"] == "created"

        ok2, res2 = execute_registered_tool(
            db1, "save_memory", {"key": "meeting_preference", "value": "afternoon"}
        )
        assert ok2 is True
        assert res2["status"] == "updated"

        execute_registered_tool(
            db1, "create_task", {"title": "Survives server restart"}
        )

    engine1.dispose()

    # Simulate backend restart by creating a brand-new SQLAlchemy engine against the same file.
    engine2 = create_db_engine(f"sqlite:///{sqlite_db_path}")
    init_db(engine2)
    session_factory2 = sessionmaker(bind=engine2, autocommit=False, autoflush=False, class_=Session)

    with session_factory2() as db2:
        ok_mem, mem_res = execute_registered_tool(db2, "retrieve_memory", {})
        assert ok_mem is True
        assert mem_res["count"] == 1
        assert mem_res["memories"][0]["key"] == "meeting_preference"
        assert mem_res["memories"][0]["value"] == "afternoon"

        ok_tasks, task_res = execute_registered_tool(db2, "list_tasks", {})
        assert ok_tasks is True
        assert task_res["count"] == 1
        assert task_res["tasks"][0]["title"] == "Survives server restart"

    engine2.dispose()
