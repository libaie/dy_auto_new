"""Batch device choices and time filters must survive creation and dispatch."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import configure_engine
from app.db_models import (
    Account, AccountGroup, AccountGroupMember, Base, Channel, ContentTemplate, Device,
)
from app.models import TaskStatus
from app.routers.tasks import (
    TaskBatchCreateRequest, TaskCreateRequest, batch_create_tasks,
    create_task as create_single_task,
)
from app.services.content_service import content_service
from app.services.stats_service import stats_service
from app.services.task_service import task_service
from app.ws_manager import pair_ws_manager


@pytest.fixture
def batch_db(monkeypatch):
    """Keep all scheduling state synthetic and separate from shared test seeds."""
    engine = create_engine("sqlite:///:memory:")
    configure_engine(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(pair_ws_manager, "broadcast_to_devices", AsyncMock())
    monkeypatch.setattr(pair_ws_manager, "broadcast_to_admins", AsyncMock())
    with Session(engine) as db:
        db.add_all([
            Account(id="account-a", nickname="Synthetic account A"),
            Account(id="account-b", nickname="Synthetic account B"),
            AccountGroup(id="group-a", name="Synthetic group A"),
            AccountGroup(id="group-b", name="Synthetic group B"),
        ])
        db.flush()
        db.add_all([
            AccountGroupMember(group_id="group-a", account_id="account-a"),
            AccountGroupMember(group_id="group-b", account_id="account-b"),
            Device(id="selected-device", name="Selected synthetic device", status="online"),
            Device(id="other-device", name="Other synthetic device", status="online"),
        ])
        db.commit()
        yield db
    engine.dispose()


def _batch(db, *, task_type="search_like", params=None, device_id=None, selection=None):
    request = TaskBatchCreateRequest(
        type=task_type,
        params=params or {"keyword": "alpha", "keywords": ["alpha"], "count": 1},
        device_id=device_id,
        **(selection or {"group_ids": ["group-a"]}),
    )
    return asyncio.run(batch_create_tasks(request, db, (None, "admin")))


def _complete(db, task):
    task_service.report_result(db, task.id, TaskStatus.COMPLETED, result={})


def test_directed_keyword_batch_cannot_be_claimed_by_another_device(batch_db):
    _batch(batch_db, device_id="selected-device")

    assert task_service.get_pending_task(batch_db, "other-device") is None
    claimed = task_service.get_pending_task(batch_db, "selected-device")
    assert claimed is not None
    assert claimed.device_id == "selected-device"
    assert claimed.params["keyword"] == "alpha"


def test_directed_batch_delivers_every_keyword_with_business_params(batch_db):
    # A directed task can override account binding, just like single creation.
    batch_db.get(Device, "selected-device").bound_account_id = "account-a"
    batch_db.get(Device, "other-device").bound_account_id = "account-b"
    stats_service.increment(batch_db, "account-a", "search_like", count=3)
    batch_db.commit()
    response = _batch(
        batch_db,
        task_type="reply_comment",
        device_id="selected-device",
        selection={"group_ids": ["group-a", "group-b"]},
        params={
            "keyword": "alpha", "keywords": ["alpha", "beta", "gamma", "delta"],
            "skip_reply": True, "prompt_template_id": "synthetic-industry-template",
            "content": "synthetic content", "count": -1, "video_count": 2,
            "max_follows": 3, "max_dms": 2, "sort_by": "latest",
            "max_age_days": 2, "max_age_unit": "hours",
        },
    )

    assert response == {"created": 4, "mode": "direct"}
    assert batch_db.query(Channel).count() == 0
    # The existing round-robin rule starts with the least-used account.
    expected = [
        ("alpha", "account-b"), ("beta", "account-a"),
        ("gamma", "account-b"), ("delta", "account-a"),
    ]
    for keyword, account_id in expected:
        assert task_service.get_pending_task(batch_db, "other-device") is None
        task = task_service.get_pending_task(batch_db, "selected-device")
        assert task is not None
        assert (task.params["keyword"], task.account_id) == (keyword, account_id)
        assert task.device_id == "selected-device"
        assert task.params["skip_reply"] is True
        assert task.params["prompt_template_id"] == "synthetic-industry-template"
        assert task.params["content"] == "synthetic content"
        assert task.params["count"] == -1
        assert task.params["video_count"] == 2
        assert task.params["max_follows"] == 3
        assert task.params["max_dms"] == 2
        assert task.params["sort_by"] == "latest"
        assert task.params["max_age_seconds"] == 7200
        assert "keywords" not in task.params
        _complete(batch_db, task)
    assert task_service.get_pending_task(batch_db, "selected-device") is None


@pytest.mark.parametrize("selection", [
    {"group_ids": ["group-a", "group-b"]},
    {"account_ids": ["account-a", "account-b"]},
])
def test_automatic_batch_keeps_channel_routing_across_groups(batch_db, selection):
    batch_db.get(Device, "selected-device").bound_account_id = "account-a"
    batch_db.get(Device, "other-device").bound_account_id = "account-b"
    batch_db.commit()
    response = _batch(
        batch_db, selection=selection,
        params={"keyword": "alpha", "keywords": ["alpha", "beta", "gamma", "delta"], "count": 1},
    )
    assert response == {"created": 4, "mode": "channel"}
    assert batch_db.query(Channel).count() == 1
    expected = [
        ("selected-device", "alpha", "account-a"), ("other-device", "beta", "account-b"),
        ("selected-device", "gamma", "account-a"), ("other-device", "delta", "account-b"),
    ]
    for device_id, keyword, account_id in expected:
        task = task_service.get_pending_task(batch_db, device_id)
        assert task is not None
        assert (task.params["keyword"], task.account_id) == (keyword, account_id)
        _complete(batch_db, task)
    assert task_service.get_pending_task(batch_db, "selected-device") is None
    assert task_service.get_pending_task(batch_db, "other-device") is None


@pytest.mark.parametrize("mode", ["single", "directed_batch", "channel"])
@pytest.mark.parametrize("task_type", ["reply_comment", "collect"])
@pytest.mark.parametrize("age,unit,expected_seconds", [
    (2, "hours", 7200), (3, "minutes", 180), (4, "seconds", 4),
    (-1, "hours", -1), (2, None, 172800),
])
def test_age_filter_reaches_dispatch_consistently(
    batch_db, mode, task_type, age, unit, expected_seconds,
):
    params = {"keyword": "alpha", "count": 1, "max_age_days": age}
    if unit is not None:
        params["max_age_unit"] = unit
    if mode == "single":
        request = TaskCreateRequest(
            type=task_type, account_id="account-a", device_id="selected-device", params=params,
        )
        asyncio.run(create_single_task(request, batch_db, (None, "admin")))
    else:
        _batch(
            batch_db, task_type=task_type, params=params,
            device_id="selected-device" if mode == "directed_batch" else None,
        )

    task = task_service.get_pending_task(batch_db, "selected-device")
    assert task is not None
    assert task.params.get("max_age_seconds") == expected_seconds
    assert task.params["max_age_days"] == age
    if unit is not None:
        assert task.params["max_age_unit"] == unit


def test_directed_batch_resolves_content_template_for_each_keyword(batch_db, monkeypatch):
    batch_db.add(ContentTemplate(
        id="synthetic-template", name="Synthetic content template",
        body="Response for {keyword}", variables=["keyword"],
    ))
    batch_db.commit()
    # Replace only the external generation boundary; DB template lookup and
    # per-keyword variable substitution remain the production implementations.
    monkeypatch.setattr(content_service, "_generate_content", AsyncMock(return_value="generated fallback"))
    _batch(
        batch_db, task_type="search_comment", device_id="selected-device",
        params={
            "keyword": "alpha", "keywords": ["alpha", "beta"], "count": 1,
            "content_template_id": "synthetic-template",
        },
    )

    for expected_content in ["Response for alpha", "Response for beta"]:
        task = task_service.get_pending_task(batch_db, "selected-device")
        assert task is not None
        assert task.params["content"] == expected_content
        assert task.params["content_template_id"] == "synthetic-template"
        _complete(batch_db, task)
