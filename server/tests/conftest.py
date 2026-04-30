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


@pytest.fixture(autouse=True)
def _rollback_after_test(test_db):
    """Rollback any DB changes after each test for isolation."""
    yield
    # Create a session to rollback uncommitted changes
    TestSession = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    session = TestSession()
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def admin_auth_override():
    """Override admin auth for all tests to pass without JWT."""
    from app.deps import verify_admin_token
    app.dependency_overrides[verify_admin_token] = lambda: "test-user"
    yield
    app.dependency_overrides.pop(verify_admin_token, None)


@pytest.fixture
def real_auth():
    """Temporarily disable auth override to test real JWT authentication."""
    from app.deps import verify_admin_token
    saved = app.dependency_overrides.pop(verify_admin_token, None)
    yield
    if saved is not None:
        app.dependency_overrides[verify_admin_token] = saved


@pytest.fixture
def db():
    """Get a test DB session from the conftest override."""
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()
