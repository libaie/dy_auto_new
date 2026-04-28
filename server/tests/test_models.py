import pytest
from datetime import datetime
from app.models import Task, TaskType, TaskStatus, AccountConfig, SelectorConfig, SelectorStrategy


def test_task_creation():
    task = Task(
        id="test-001",
        type=TaskType.NURTURE,
        account_id="acc-001",
        device_id="dev-001",
        params={"duration": 30},
    )
    assert task.id == "test-001"
    assert task.type == TaskType.NURTURE
    assert task.status == TaskStatus.PENDING
    assert task.params == {"duration": 30}


def test_task_status_transitions():
    task = Task(
        id="test-002",
        type=TaskType.SEARCH_COMMENT,
        account_id="acc-001",
        device_id="dev-001",
        params={"keyword": "美食", "count": 5},
    )
    assert task.status == TaskStatus.PENDING

    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now()
    assert task.status == TaskStatus.RUNNING

    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now()
    task.result = {"success_count": 4, "fail_count": 1}
    assert task.status == TaskStatus.COMPLETED
    assert task.result["success_count"] == 4


def test_account_config():
    account = AccountConfig(
        id="acc-001",
        nickname="测试账号",
        douyin_id="test_user_123",
        daily_limits={"likes": 50, "comments": 20},
    )
    assert account.id == "acc-001"
    assert account.daily_limits["likes"] == 50


def test_selector_config():
    selector = SelectorConfig(
        action_name="like_video",
        strategies=[
            SelectorStrategy(type="text", value="赞", priority=1),
            SelectorStrategy(type="id", value="com.ss.android.ugc.aweme:id/like_btn", priority=2),
        ],
    )
    assert selector.action_name == "like_video"
    assert len(selector.strategies) == 2
    assert selector.strategies[0].type == "text"
