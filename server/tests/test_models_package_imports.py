def test_legacy_app_models_imports_remain_available():
    from app.models import Task, TaskStatus, TaskType

    assert TaskType.NURTURE.value == "nurture"
    assert TaskStatus.PENDING.value == "pending"
    task = Task(type=TaskType.NURTURE, account_id="acc-001")
    assert task.status == TaskStatus.PENDING
