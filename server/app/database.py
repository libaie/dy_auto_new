"""Database engine, session factory, and FastAPI dependency."""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db_models import Base

SERVER_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = SERVER_DIR / "app" / "data" / "dy_auto.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# SQLite needs check_same_thread=False for FastAPI's multi-threaded request handling
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Create all tables. Called once at startup."""
    # Ensure data directory exists for SQLite
    if DATABASE_URL.startswith("sqlite"):
        Path(DATABASE_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session per request, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
