"""Shared test fixtures — uses a fresh in-memory SQLite DB per test session."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db_models import Base
from app.database import get_db
from app.main import app
from app.seed import seed_accounts, seed_selectors


@pytest.fixture(scope="session", autouse=True)
def test_db():
    """Create a test database once per session, seed it, and override get_db."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    Base.metadata.create_all(bind=test_engine)

    # Seed with test data
    db = TestSession()
    seed_accounts(db)
    seed_selectors(db)
    db.close()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield test_engine
    app.dependency_overrides.clear()
    test_engine.dispose()


@pytest.fixture
def db():
    """Get a test DB session from the conftest override."""
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()
