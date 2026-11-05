"""Task choices must survive the admin API, persistence and device polling."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db_models import (
    Account, AccountGroup, AccountGroupMember, Channel, ChannelItem,
    DailyStats, Device, StatsEvent, Task,
)
from app.main import app


@pytest.fixture
def task_route(db):
    tag = str(uuid.uuid4())
    account = Account(id=tag, nickname="Synthetic task account", user_id="test-user-id")
    group = AccountGroup(id=tag, name="Synthetic task group", user_id="test-user-id")
    device = Device(id=tag, name="Synthetic device", device_secret=tag,
                    bound_account_id=tag, user_id="test-user-id", status="online")
    db.add_all([account, group])
    db.flush()
    db.add_all([device, AccountGroupMember(group_id=tag, account_id=tag)])
    db.commit()
    yield {"id": tag, "client": TestClient(app), "headers": {"X-Device-Secret": tag}}
    db.rollback()
    channels = db.query(Channel.id).filter(Channel.group_id == tag).scalar_subquery()
    db.query(ChannelItem).filter(ChannelItem.channel_id.in_(channels)).delete(synchronize_session=False)
    db.query(StatsEvent).filter(StatsEvent.account_id == tag).delete(synchronize_session=False)
    db.query(DailyStats).filter(DailyStats.account_id == tag).delete(synchronize_session=False)
    db.query(Task).filter(Task.account_id == tag).delete(synchronize_session=False)
    db.query(Channel).filter(Channel.group_id == tag).delete(synchronize_session=False)
    db.query(Device).filter(Device.id == tag).delete(synchronize_session=False)
    db.query(AccountGroupMember).filter(AccountGroupMember.group_id == tag).delete(synchronize_session=False)
    db.query(AccountGroup).filter(AccountGroup.id == tag).delete(synchronize_session=False)
    db.query(Account).filter(Account.id == tag).delete(synchronize_session=False)
    db.commit()


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("skip_reply", [True, False])
def test_reply_choice_reaches_device_through_actual_creation_and_poll(task_route, batch, skip_reply):
    client, tag = task_route["client"], task_route["id"]
    payload = {
        "type": "reply_comment",
        "params": {
            "keyword": "synthetic keyword", "count": 1,
            "skip_reply": skip_reply, "prompt_template_id": "synthetic-industry-template",
        },
    }
    if batch:
        payload["group_ids"] = [tag]
    else:
        payload["account_id"] = tag
    created = client.post("/api/tasks/batch" if batch else "/api/tasks", json=payload)
    assert created.status_code == 200, created.text

    polled = client.get("/api/device/poll", params={"device_id": tag}, headers=task_route["headers"])
    assert polled.status_code == 200, polled.text
    task = polled.json()["task"]
    assert task is not None
    assert task["params"].get("skip_reply") is skip_reply
    assert task["params"]["prompt_template_id"] == "synthetic-industry-template"
    assert task["lease_id"]
