"""SQLAlchemy engine, non-destructive SQLite migrations, and session dependencies."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
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


def _sqlite_table_columns(conn: Any, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _apply_sqlite_migrations(target_engine: Engine) -> None:
    """Non-destructively migrate existing Day 3 SQLite tables to multi-user schemas."""
    if not str(target_engine.url).startswith("sqlite"):
        return

    with target_engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }

        if "users" in tables:
            cols = _sqlite_table_columns(conn, "users")
            if "timezone" not in cols:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'")
                )

        if "tasks" in tables:
            cols = _sqlite_table_columns(conn, "tasks")
            if "user_id" not in cols:
                conn.execute(
                    text("ALTER TABLE tasks ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
                )

        if "conversations" in tables:
            cols = _sqlite_table_columns(conn, "conversations")
            if "user_id" not in cols:
                conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
                )

        if "memories" in tables:
            cols = _sqlite_table_columns(conn, "memories")
            if "user_id" not in cols:
                # Rebuild memories table cleanly to change UNIQUE(key) -> UNIQUE(user_id, key)
                # while preserving every existing Day 3 memory row under user_id=1.
                conn.execute(
                    text(
                        """
                        CREATE TABLE memories_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL DEFAULT 1 REFERENCES users(id) ON DELETE CASCADE,
                            key VARCHAR(150) NOT NULL,
                            value TEXT NOT NULL,
                            created_at DATETIME,
                            updated_at DATETIME,
                            CONSTRAINT uq_memories_user_key UNIQUE (user_id, key)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO memories_new (id, user_id, key, value, created_at, updated_at)
                        SELECT id, 1, key, value, created_at, updated_at FROM memories
                        """
                    )
                )
                conn.execute(text("DROP TABLE memories"))
                conn.execute(text("ALTER TABLE memories_new RENAME TO memories"))
                conn.execute(text("CREATE INDEX ix_memories_user_id ON memories (user_id)"))
                conn.execute(text("CREATE INDEX ix_memories_key ON memories (key)"))


def init_db(target_engine: Engine | None = None) -> None:
    """Apply safe migrations, create missing tables, and ensure local demo user exists."""
    active_engine = target_engine or engine
    _apply_sqlite_migrations(active_engine)
    Base.metadata.create_all(bind=active_engine)

    session_factory = sessionmaker(
        bind=active_engine, autocommit=False, autoflush=False, class_=Session
    )
    with session_factory() as db:
        demo_user = db.query(User).filter(User.id == 1).first()
        if demo_user is None:
            db.add(
                User(
                    id=1,
                    name="LifeDesk User",
                    email="demo@lifedesk.local",
                    timezone=get_settings().default_timezone,
                )
            )
            db.commit()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session per FastAPI request and close it cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
