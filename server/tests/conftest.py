"""Shared test fixtures — uses a fresh in-memory SQLite DB per test session."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db_models import Base, Task, ChainInstance, DailyStats, Account, AccountGroup, AccountGroupMember, Channel, ChannelItem, Character, Scene, Series, Episode, PipelineRun, AuditReport, series_characters, series_scenes
from app.database import get_db
from app.main import app
from app.seed import seed_accounts, seed_selectors

# Tables to clean between tests (order matters for FK constraints)
_CLEANUP_TABLES = [
    Task, DailyStats, AccountGroupMember, AccountGroup, ChainInstance,
    ChannelItem, Channel,
    AuditReport, PipelineRun, Episode,  # weak FK to Series/Episode
]
_CLEANUP_M2M = [series_characters, series_scenes, Series, Character, Scene]  # M2M first, then parent tables


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
def _isolate_test(test_db):
    """Clean committed data before each test for full isolation."""
    TestSession = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    session = TestSession()
    for model in _CLEANUP_TABLES:
        session.query(model).delete()
    # Clean M2M tables first, then parent tables
    for table in _CLEANUP_M2M:
        if hasattr(table, 'delete'):
            session.execute(table.delete())
        else:
            session.query(table).delete()
    session.commit()
    session.close()
    # Reset login rate limiter state (test_admin_auth.py fills it up)
    from app.routers.auth import _failed_attempts
    _failed_attempts.clear()
    yield


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


def setup_group(db, group_id="grp-001", account_ids=None):
    """Helper: create a group with active accounts."""
    if account_ids is None:
        account_ids = ["acc-001", "acc-002"]
    group = AccountGroup(id=group_id, name=f"test-{group_id}")
    db.add(group)
    for aid in account_ids:
        acc = Account(id=aid, nickname=f"nick-{aid}", status="active")
        db.add(acc)
        db.add(AccountGroupMember(group_id=group_id, account_id=aid))
    db.flush()
    return group
