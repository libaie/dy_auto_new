"""An explicit device target survives retries until that device is removed."""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import bj_now
from app.database import configure_engine
from app.db_models import (
    Account, AccountGroup, AccountGroupMember, Base, ChainInstance, ChainTemplate, Device, Task, User,
)
from app.models import TaskStatus, TaskType
from app.routers.chains import get_instance
from app.routers.devices import delete_device
from app.routers.tasks import TaskBatchCreateRequest, batch_create_tasks
from app.services.chain_service import _task_to_push_dict
from app.services.task_service import task_service
from app.ws_manager import pair_ws_manager


@pytest.fixture
def retry_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    configure_engine(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("TASK_STALE_MINUTES", "10")
    for method in ("broadcast_to_devices", "broadcast_to_admins", "send_to_device", "disconnect_device"):
        monkeypatch.setattr(pair_ws_manager, method, AsyncMock())
    with Session(engine) as db:
        db.add_all([
            User(id="owner", username="synthetic-owner", password_hash="unused"),
            User(id="other-owner", username="synthetic-other-owner", password_hash="unused"),
        ])
        db.flush()
        db.add_all([
            Account(id="account", nickname="Synthetic account", user_id="owner"),
            AccountGroup(id="group", name="Synthetic group", user_id="owner"),
            Device(id="target", name="Selected synthetic device", user_id="owner"),
            Device(id="alternate", name="Same-owner alternate device", user_id="owner"),
            Device(id="outsider", name="Other-owner device", user_id="other-owner"),
        ])
        db.flush()
        db.add(AccountGroupMember(group_id="group", account_id="account"))
        db.commit()
        yield db
    engine.dispose()


def _create(db, *, source="service", target="target", params=None):
    params = params or {"keyword": "alpha", "count": 1}
    if source == "batch":
        request = TaskBatchCreateRequest(
            type="search_like", group_ids=["group"], device_id=target, params=params,
        )
        response = asyncio.run(batch_create_tasks(request, db, ("owner", "operator")))
        assert response == {"created": 1, "mode": "direct"}
        return db.query(Task).one().id
    if source == "legacy_pending":
        task = Task(
            type="search_like", account_id="account", device_id=target,
            user_id="owner", params=params, status="pending",
        )
        db.add(task)
        db.commit()
        return task.id
    return task_service.create_task(
        db, TaskType.SEARCH_LIKE, "account", params, device_id=target, user_id="owner",
    ).id


def _expire(db, task_id, *, online=False):
    now = bj_now()
    row = db.get(Task, task_id)
    row.started_at = now - timedelta(minutes=11)
    device = db.get(Device, row.device_id)
    device.last_seen_at = now if online else now - timedelta(minutes=11)
    db.commit()
    assert task_service.recover_stale_tasks(db, now=now) == [task_id]


@pytest.mark.parametrize("source", ["service", "batch", "legacy_pending"])
def test_reported_failure_keeps_explicit_target_across_retries(retry_db, source):
    task_id = _create(retry_db, source=source)
    task = task_service.get_pending_task(retry_db, "target")
    assert task is not None and task.id == task_id
    for retry_count in (1, 2):
        old_lease = task.lease_id
        task_service.report_result(retry_db, task_id, TaskStatus.FAILED, result={"error": "synthetic failure"})
        assert task_service.get_pending_task(retry_db, "outsider") is None
        assert task_service.get_pending_task(retry_db, "alternate") is None
        task = task_service.get_pending_task(retry_db, "target")
        assert task is not None and task.id == task_id
        assert task.retry_count == retry_count
        assert task.lease_id and task.lease_id != old_lease
        assert task.params == {"keyword": "alpha", "count": 1}


@pytest.mark.parametrize("source", ["service", "batch"])
@pytest.mark.parametrize("online", [False, True])
def test_timeout_recovery_keeps_explicit_target(retry_db, source, online):
    task_id = _create(retry_db, source=source)
    task = task_service.get_pending_task(retry_db, "target")
    old_lease = task.lease_id
    _expire(retry_db, task_id, online=online)

    recovered = retry_db.get(Task, task_id)
    assert recovered.status == "pending"
    assert recovered.device_id == "target"
    assert recovered.retry_count == 1
    assert recovered.lease_id is None
    assert task_service.get_pending_task(retry_db, "outsider") is None
    assert task_service.get_pending_task(retry_db, "alternate") is None
    retried = task_service.get_pending_task(retry_db, "target")
    assert retried is not None and retried.id == task_id
    assert retried.lease_id and retried.lease_id != old_lease


@pytest.mark.parametrize("reason", ["failure", "timeout"])
def test_automatic_task_can_move_to_another_same_owner_device(retry_db, reason):
    task_id = _create(retry_db, target=None)
    first = task_service.get_pending_task(retry_db, "target")
    assert first is not None and first.id == task_id
    if reason == "failure":
        task_service.report_result(retry_db, task_id, TaskStatus.FAILED)
    else:
        _expire(retry_db, task_id)

    assert retry_db.get(Task, task_id).device_id is None
    assert task_service.get_pending_task(retry_db, "outsider") is None
    replacement = task_service.get_pending_task(retry_db, "alternate")
    assert replacement is not None and replacement.id == task_id
    assert replacement.retry_count == 1
    assert replacement.device_id == "alternate"


@pytest.mark.parametrize("target", [None, "target"])
def test_server_owns_target_metadata_without_mutating_or_exposing_params(retry_db, target):
    params = {"keyword": "alpha", "count": 1, "_target_device_id": "outsider"}
    task_id = _create(retry_db, target=target, params=params)
    assert params == {"keyword": "alpha", "count": 1, "_target_device_id": "outsider"}
    assert task_service.get_task(retry_db, task_id).params == {"keyword": "alpha", "count": 1}
    assert task_service.list_tasks(retry_db)[0].params == {"keyword": "alpha", "count": 1}

    stored = retry_db.get(Task, task_id).params
    assert stored.get("_target_device_id") == target
    if target is None:
        assert "_target_device_id" not in stored
    first_device = "target" if target else "alternate"
    first = task_service.get_pending_task(retry_db, first_device)
    assert first is not None and first.id == task_id
    assert first.params == {"keyword": "alpha", "count": 1}
    task_service.report_result(retry_db, task_id, TaskStatus.FAILED)
    if target:
        assert task_service.get_pending_task(retry_db, "alternate") is None
    # A caller-supplied reserved key cannot direct the retry to another owner.
    assert task_service.get_pending_task(retry_db, "outsider") is None
    assert task_service.get_pending_task(retry_db, "target").id == task_id


def test_direct_claim_ignores_untrusted_target_in_existing_pending_params(retry_db):
    task_id = _create(
        retry_db, source="legacy_pending", target=None,
        params={"keyword": "alpha", "count": 1, "_target_device_id": "outsider"},
    )
    assert task_service.get_pending_task(retry_db, "target").id == task_id
    task_service.report_result(retry_db, task_id, TaskStatus.FAILED)
    assert "_target_device_id" not in retry_db.get(Task, task_id).params
    assert task_service.get_pending_task(retry_db, "outsider") is None
    assert task_service.get_pending_task(retry_db, "alternate").id == task_id


@pytest.mark.parametrize("running", [False, True])
def test_device_deletion_releases_target_even_if_device_id_is_reused(retry_db, running):
    task_id = _create(retry_db)
    if running:
        assert task_service.get_pending_task(retry_db, "target").id == task_id
    response = asyncio.run(delete_device("target", retry_db, ("owner", "operator")))
    assert response == {"deleted": True, "id": "target"}
    assert retry_db.get(Device, "target") is None
    released = retry_db.get(Task, task_id)
    assert released.status == "pending"
    assert released.device_id is None
    assert released.lease_id is None
    assert "_target_device_id" not in released.params
    assert task_service.get_pending_task(retry_db, "outsider") is None
    assert task_service.get_pending_task(retry_db, "alternate").id == task_id

    retry_db.add(Device(id="target", name="Recreated synthetic device", user_id="owner"))
    retry_db.commit()
    task_service.report_result(retry_db, task_id, TaskStatus.FAILED)
    # Recreating the old device ID must not resurrect the removed reservation.
    assert task_service.get_pending_task(retry_db, "alternate").id == task_id


def test_retry_releases_target_that_no_longer_exists(retry_db):
    task_id = _create(retry_db)
    assert task_service.get_pending_task(retry_db, "target").id == task_id
    # Simulate an older cleanup path that removed the device without knowing
    # about the new metadata. ORM clears the device FK, but keeps task params.
    retry_db.delete(retry_db.get(Device, "target"))
    retry_db.commit()
    task_service.report_result(retry_db, task_id, TaskStatus.FAILED)
    assert "_target_device_id" not in retry_db.get(Task, task_id).params
    assert task_service.get_pending_task(retry_db, "outsider") is None
    assert task_service.get_pending_task(retry_db, "alternate").id == task_id


def test_chain_detail_and_push_only_expose_business_params(retry_db):
    retry_db.add(ChainTemplate(
        id="chain-template", name="Synthetic chain template", user_id="owner",
        steps=[{"step_order": 1, "type": "search_like", "params": {"keyword": "alpha", "count": 1}}],
    ))
    retry_db.flush()
    retry_db.add(ChainInstance(
        id="chain-instance", template_id="chain-template", account_id="account",
        device_id="target", user_id="owner", total_steps=1, status="running",
    ))
    retry_db.flush()
    retry_db.add(Task(
        id="chain-task", type="search_like", account_id="account", device_id="target",
        user_id="owner", chain_instance_id="chain-instance", step_order=1,
        params={"keyword": "alpha", "count": 1}, status="pending",
    ))
    retry_db.commit()
    assert task_service.get_pending_task(retry_db, "target").id == "chain-task"
    stored = retry_db.get(Task, "chain-task")
    assert stored.params["_target_device_id"] == "target"

    detail = get_instance("chain-instance", retry_db, ("owner", "operator"))
    assert detail["tasks"][0]["params"] == {"keyword": "alpha", "count": 1}
    assert _task_to_push_dict(stored)["params"] == {"keyword": "alpha", "count": 1}
    assert stored.params["_target_device_id"] == "target"
