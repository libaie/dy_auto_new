"""Task service tests — DB-backed."""
import pytest
from app.models import TaskType, TaskStatus
from app.services.task_service import task_service
from app.database import SessionLocal, get_db
from app.main import app


@pytest.fixture
def db():
    """Get a test DB session from the conftest override."""
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()


def test_create_task(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 30})
    assert task.type == TaskType.NURTURE
    assert task.account_id == "acc-001"
    assert task.status == TaskStatus.PENDING


def test_get_pending_task(db):
    task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    claimed = task_service.get_pending_task(db, "dev-001")
    assert claimed is not None
    assert claimed.status == TaskStatus.RUNNING
    assert claimed.device_id == "dev-001"


def test_no_duplicate_assignment(db):
    task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    first = task_service.get_pending_task(db, "dev-001")
    second = task_service.get_pending_task(db, "dev-002")
    assert first is not None
    # second may be None or a different task — never the same
    if second is not None:
        assert second.id != first.id


def test_report_result(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-001")
    result_task = task_service.report_result(db, task.id, TaskStatus.COMPLETED, {"success_count": 3})
    assert result_task.status == TaskStatus.COMPLETED
    assert result_task.result["success_count"] == 3


def test_report_failure_increments_retry(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-001")
    failed = task_service.report_result(db, task.id, TaskStatus.FAILED, {"details": "error"})
    assert failed.status == TaskStatus.PENDING  # re-queued
    assert failed.retry_count == 1


def test_max_retries(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    for i in range(3):
        task_service.get_pending_task(db, "dev-001")
        task = task_service.report_result(db, task.id, TaskStatus.FAILED, {"details": f"fail {i}"})
    assert task.status == TaskStatus.FAILED


def test_list_tasks(db):
    tasks = task_service.list_tasks(db)
    assert len(tasks) > 0


def test_get_nonexistent_task(db):
    task = task_service.get_task(db, "nonexistent-id")
    assert task is None


def test_report_result_nonexistent_task(db):
    with pytest.raises(ValueError, match="not found"):
        task_service.report_result(db, "nonexistent-id", TaskStatus.COMPLETED)


def test_list_tasks_with_pagination(db):
    tasks_page1 = task_service.list_tasks(db, skip=0, limit=2)
    tasks_page2 = task_service.list_tasks(db, skip=2, limit=2)
    assert len(tasks_page1) <= 2
    # Pages should not overlap (if enough tasks exist)
    if len(tasks_page1) == 2 and len(tasks_page2) > 0:
        assert tasks_page1[0].id != tasks_page2[0].id


def test_count_tasks(db):
    total = task_service.count_tasks(db)
    assert total > 0
    pending_count = task_service.count_tasks(db, status=TaskStatus.PENDING)
    assert pending_count >= 0
    assert pending_count <= total


def test_cancel_pending_task(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    cancelled = task_service.cancel_task(db, task.id)
    assert cancelled.status == TaskStatus.CANCELLED


def test_cancel_running_task(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-001")
    cancelled = task_service.cancel_task(db, task.id)
    assert cancelled.status == TaskStatus.CANCELLED


def test_cancel_completed_task_fails(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-001")
    task_service.report_result(db, task.id, TaskStatus.COMPLETED, {"success_count": 1})
    with pytest.raises(ValueError, match="Cannot cancel"):
        task_service.cancel_task(db, task.id)


def test_cancel_nonexistent_task(db):
    with pytest.raises(ValueError, match="not found"):
        task_service.cancel_task(db, "nonexistent-id")


def test_check_cancelled_running(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-cancel-check")
    task_service.cancel_task(db, task.id)
    result = task_service.check_cancelled_running(db, "dev-cancel-check")
    assert result is not None
    assert result.id == task.id


def test_check_cancelled_running_none(db):
    result = task_service.check_cancelled_running(db, "dev-no-cancel")
    assert result is None


def test_quota_blocks_task_assignment(db):
    """When ALL pending tasks are over quota, get_pending_task returns None."""
    from app.services.stats_service import stats_service
    from app.db_models import Task as DBTask, Account

    quota_account = "acc-quota-test"
    # Create account first
    account = Account(id=quota_account, nickname="quota-test", daily_limits={"likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15})
    db.add(account)
    db.commit()

    # Exhaust likes quota (default 50)
    stats_service.increment(db, quota_account, "search_like", count=50)

    # Cancel all existing pending tasks to isolate this test
    db.query(DBTask).filter(DBTask.status == TaskStatus.PENDING.value).update(
        {"status": TaskStatus.CANCELLED.value}
    )
    db.commit()

    # Create ONLY a search_like task for the quota-exhausted account
    task_service.create_task(db, TaskType.SEARCH_LIKE, quota_account, {"keyword": "test"})

    # Try to claim — should get None because the only pending task is over quota
    claimed = task_service.get_pending_task(db, "dev-quota")
    assert claimed is None

    # Verify the task is still pending (not silently dropped)
    remaining = db.query(DBTask).filter(DBTask.status == TaskStatus.PENDING.value).all()
    assert len(remaining) == 1
    assert remaining[0].account_id == quota_account


def test_quota_allows_non_exhausted_tasks(db):
    """Tasks of non-exhausted types should still be assignable."""
    from app.services.stats_service import stats_service
    from app.db_models import Task as DBTask, Account

    quota_account2 = "acc-quota-test2"
    # Create account first
    account = Account(id=quota_account2, nickname="quota-test2", daily_limits={"likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15})
    db.add(account)
    db.commit()

    stats_service.increment(db, quota_account2, "search_like", count=50)

    # Cancel all existing pending tasks to isolate this test
    db.query(DBTask).filter(DBTask.status == TaskStatus.PENDING.value).update(
        {"status": TaskStatus.CANCELLED.value}
    )
    db.commit()

    # Create a search_comment task (comment quota not exhausted)
    task_service.create_task(db, TaskType.SEARCH_COMMENT, quota_account2, {"keyword": "test"})
    claimed = task_service.get_pending_task(db, "dev-quota2")
    assert claimed is not None
    assert claimed.type == TaskType.SEARCH_COMMENT


def test_report_completed_increments_stats(db):
    """Completing a task should increment daily stats."""
    from app.services.stats_service import stats_service
    from app.db_models import Account

    stats_account = "acc-stats-test"
    # Create account first
    account = Account(id=stats_account, nickname="stats-test", daily_limits={"likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15})
    db.add(account)
    db.commit()

    task = task_service.create_task(db, TaskType.SEARCH_LIKE, stats_account, {"keyword": "test"})
    task_service.get_pending_task(db, "dev-stats")

    counts_before = stats_service.get_today_counts(db, stats_account)
    task_service.report_result(db, task.id, TaskStatus.COMPLETED, {"success_count": 3})
    counts_after = stats_service.get_today_counts(db, stats_account)

    assert counts_after["likes"] - counts_before["likes"] == 3


def test_all_candidates_over_quota_returns_none(db):
    """When all 10+ candidates are over quota, returns None."""
    from app.services.stats_service import stats_service
    from app.db_models import Task as DBTask, Account

    # Cancel all existing pending tasks
    db.query(DBTask).filter(DBTask.status == TaskStatus.PENDING.value).update(
        {"status": TaskStatus.CANCELLED.value}
    )
    db.commit()

    # Create 12 tasks for quota-exhausted accounts
    for i in range(12):
        acc = f"acc-overquota-{i}"
        account = Account(id=acc, nickname=f"overquota-{i}", daily_limits={"likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15})
        db.add(account)
        db.commit()
        stats_service.increment(db, acc, "search_like", count=50)
        task_service.create_task(db, TaskType.SEARCH_LIKE, acc, {"keyword": "test"})

    claimed = task_service.get_pending_task(db, "dev-overquota")
    assert claimed is None
