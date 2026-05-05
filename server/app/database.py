"""Database engine, session factory, and FastAPI dependency."""
import os
import logging
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from app.db_models import Base

logger = logging.getLogger(__name__)

SERVER_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = SERVER_DIR / "app" / "data" / "dy_auto.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# SQLite needs check_same_thread=False for FastAPI's multi-threaded request handling
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def _migrate_add_columns():
    """Add missing columns to existing SQLite tables (safe to call repeatedly)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    insp = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in insp.get_table_names():
                continue
            existing = {col["name"] for col in insp.get_columns(table_name)}
            for col in table.columns:
                if col.name not in existing:
                    col_type = col.type.compile(engine.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    default = ""
                    if col.default is not None:
                        default_sql = col.default.arg
                        if isinstance(default_sql, bool):
                            default = f" DEFAULT {1 if default_sql else 0}"
                        elif isinstance(default_sql, str):
                            default = f" DEFAULT '{default_sql}'"
                        elif isinstance(default_sql, (int, float)):
                            default = f" DEFAULT {default_sql}"
                        elif isinstance(default_sql, (list, dict)):
                            import json as _json
                            default = f" DEFAULT '{_json.dumps(default_sql)}'"
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type} {nullable}{default}"
                    logger.info(f"Migration: {sql}")
                    conn.execute(text(sql))


def init_db():
    """Create all tables. Called once at startup."""
    # Ensure data directory exists for SQLite
    if DATABASE_URL.startswith("sqlite"):
        Path(DATABASE_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()


def get_db():
    """FastAPI dependency — yields a DB session per request, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
