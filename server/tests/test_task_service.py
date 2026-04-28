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
