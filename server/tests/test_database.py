"""Database configuration tests."""
from sqlalchemy import text
from app.database import engine


def test_sqlite_wal_mode():
    """SQLite should be in WAL journal mode for concurrent writes."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert result == "wal", f"Expected WAL mode, got {result}"


def test_sqlite_busy_timeout():
    """SQLite busy_timeout should be set to avoid SQLITE_BUSY errors."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA busy_timeout")).scalar()
    assert result >= 5000, f"Expected busy_timeout >= 5000, got {result}"
