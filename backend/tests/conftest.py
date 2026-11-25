"""Shared pytest fixtures for isolated SQLite databases and FastAPI TestClient."""

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.database import create_db_engine, get_db, init_db
from app.main import create_app


@pytest.fixture
def sqlite_db_path(tmp_path: Path) -> Path:
    """Return a temporary SQLite file path for persistence tests."""
    return tmp_path / "test_lifedesk.db"


@pytest.fixture
def db_engine(sqlite_db_path: Path) -> Generator[Engine, None, None]:
    """Create a file-backed SQLite engine with initialized schema."""
    engine = create_db_engine(f"sqlite:///{sqlite_db_path}")
    init_db(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Provide an isolated SQLAlchemy session per test."""
    factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False, class_=Session)
    with factory() as session:
        yield session


@pytest.fixture
def api_client(db_engine: Engine) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the isolated temporary SQLite database."""
    factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False, class_=Session)
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
