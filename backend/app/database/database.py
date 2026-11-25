"""SQLAlchemy engine, session management, and database initialization."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.models import Base, User


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine configured for SQLite or standard SQL."""
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, connect_args=connect_args, future=True)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


_settings = get_settings()
engine = create_db_engine(_settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def init_db(target_engine: Engine | None = None) -> None:
    """Create tables if needed and ensure the single local demo user exists."""
    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)

    session_factory = sessionmaker(
        bind=active_engine, autocommit=False, autoflush=False, class_=Session
    )
    with session_factory() as db:
        demo_user = db.query(User).filter(User.id == 1).first()
        if demo_user is None:
            db.add(User(id=1, name="LifeDesk User", email="demo@lifedesk.local"))
            db.commit()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session per FastAPI request and close it cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
