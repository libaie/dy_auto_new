import pytest
from app.models import Task, TaskType, TaskStatus
from app.services.task_service import TaskService


@pytest.fixture
def service():
    return TaskService()


def test_create_task(service):
    task = service.create_task(
        task_type=TaskType.NURTURE,
        account_id="acc-001",
        params={"duration": 30},
    )
    assert task.type == TaskType.NURTURE
    assert task.account_id == "acc-001"
    assert task.status == TaskStatus.PENDING
    assert task.id is not None


def test_get_pending_task(service):
    service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})
    task = service.get_pending_task("dev-001")
    assert task is not None
    assert task.status == TaskStatus.RUNNING
    assert task.device_id == "dev-001"
    assert task.started_at is not None


def test_no_duplicate_assignment(service):
    service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})
    task1 = service.get_pending_task("dev-001")
    task2 = service.get_pending_task("dev-002")
    assert task1 is not None
    assert task2 is None  # already claimed by dev-001


def test_report_result(service):
    task = service.create_task(TaskType.SEARCH_COMMENT, "acc-001", {"keyword": "美食", "count": 5})
    service.get_pending_task("dev-001")

    updated = service.report_result(
        task_id=task.id,
        status=TaskStatus.COMPLETED,
        result={"success_count": 4, "fail_count": 1},
    )
    assert updated.status == TaskStatus.COMPLETED
    assert updated.result["success_count"] == 4
    assert updated.completed_at is not None


def test_report_failure_increments_retry(service):
    task = service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})
    service.get_pending_task("dev-001")

    service.report_result(task.id, TaskStatus.FAILED, {"error": "UI not found"})
    updated = service.get_task(task.id)
    assert updated.retry_count == 1
    assert updated.status == TaskStatus.PENDING  # re-queued for retry


def test_max_retries(service):
    task = service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})

    for i in range(3):
        service.get_pending_task("dev-001")
        service.report_result(task.id, TaskStatus.FAILED, {"error": "fail"})

    updated = service.get_task(task.id)
    assert updated.status == TaskStatus.FAILED  # exceeded max retries
    assert updated.retry_count == 3


def test_list_tasks(service):
    service.create_task(TaskType.NURTURE, "acc-001", {"duration": 30})
    service.create_task(TaskType.SEARCH_LIKE, "acc-001", {"keyword": "美食", "count": 10})

    tasks = service.list_tasks()
    assert len(tasks) == 2

    pending = service.list_tasks(status=TaskStatus.PENDING)
    assert len(pending) == 2
