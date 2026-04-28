"""Stats service tests — daily operation counting and quota checks."""
import pytest
from app.services.stats_service import stats_service
from app.models import TaskType
from app.database import get_db
from app.db_models import Account
from app.main import app


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    session.rollback()
    gen.close()


def _create_account(db, account_id, limits=None):
    """Helper: create an Account row so check_quota can look up daily_limits."""
    if limits is None:
        limits = {"likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15}
    acc = Account(id=account_id, nickname=f"test-{account_id}", daily_limits=limits)
    db.add(acc)
    db.flush()
    return acc


def test_increment_and_get_counts(db):
    """Incrementing likes should be reflected in get_today_counts."""
    _create_account(db, "acc-stats-001")
    stats_service.increment(db, "acc-stats-001", "search_like", count=3)
    counts = stats_service.get_today_counts(db, "acc-stats-001")
    assert counts["likes"] >= 3


def test_increment_comments(db):
    _create_account(db, "acc-stats-002")
    stats_service.increment(db, "acc-stats-002", "search_comment", count=2)
    counts = stats_service.get_today_counts(db, "acc-stats-002")
    assert counts["comments"] >= 2


def test_check_quota_within_limit(db):
    """Fresh account should have quota available."""
    _create_account(db, "acc-stats-new")
    assert stats_service.check_quota(db, "acc-stats-new", "search_like") is True


def test_check_quota_exceeded(db):
    """After hitting the daily limit, quota check should return False."""
    _create_account(db, "acc-stats-limit")
    stats_service.increment(db, "acc-stats-limit", "search_like", count=50)
    assert stats_service.check_quota(db, "acc-stats-limit", "search_like") is False


def test_check_quota_exact_boundary(db):
    """At exactly the limit (used == limit), quota should be exhausted."""
    _create_account(db, "acc-stats-boundary")
    stats_service.increment(db, "acc-stats-boundary", "search_like", count=49)
    assert stats_service.check_quota(db, "acc-stats-boundary", "search_like") is True
    stats_service.increment(db, "acc-stats-boundary", "search_like", count=1)
    assert stats_service.check_quota(db, "acc-stats-boundary", "search_like") is False


def test_check_quota_unknown_account(db):
    """Non-existent account should not be blocked (fail-open)."""
    assert stats_service.check_quota(db, "nonexistent-account", "search_like") is True


def test_get_remaining_quotas(db):
    _create_account(db, "acc-stats-remaining")
    stats_service.increment(db, "acc-stats-remaining", "search_comment", count=5)
    remaining = stats_service.get_remaining_quotas(db, "acc-stats-remaining")
    assert remaining["comments"] == 15  # 20 - 5
    assert remaining["likes"] == 50     # untouched


def test_unknown_task_type_no_block(db):
    """Unknown task types should not be blocked."""
    _create_account(db, "acc-stats-unknown")
    assert stats_service.check_quota(db, "acc-stats-unknown", "unknown_type") is True
