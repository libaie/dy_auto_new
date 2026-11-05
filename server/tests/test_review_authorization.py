"""Behavior regressions for tenant ownership and event delivery boundaries."""
import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db_models import Account, AccountGroup, AccountGroupMember, Device, DevicePairRequest, Task, User, StatsEvent, DailyStats
from app.deps import create_access_token
from app.ws_manager import PairWSManager


@pytest.fixture
def identities(db, real_auth):
    tag = uuid.uuid4().hex[:12]
    users = {}
    resources = {key: {} for key in ("accounts", "devices", "tasks", "groups", "pairs")}
    for name, role in (("owner", "operator"), ("other", "operator"), ("admin", "admin")):
        user = User(id=str(uuid.uuid4()), username=f"{name}-{tag}", password_hash="unused", role=role)
        db.add(user)
        users[name] = user
    db.flush()
    for name in ("owner", "other"):
        account = Account(nickname=f"{name}-{tag}", user_id=users[name].id)
        group = AccountGroup(name=f"{name}-{tag}", user_id=users[name].id)
        db.add_all([account, group])
        db.flush()
        device = Device(name=f"{name}-{tag}", user_id=users[name].id, bound_account_id=account.id, device_secret=f"{name}-{tag}")
        db.add(device)
        db.flush()
        task = Task(type="nurture", account_id=account.id, user_id=users[name].id, device_id=device.id,
                    status="pending", params={"duration": 30}, lease_id=f"lease-{tag}-{name}")
        pair = DevicePairRequest(device_id=device.id, device_name=device.name, pairing_token=f"pair-{name}-{tag}")
        db.add_all([task, pair, AccountGroupMember(group_id=group.id, account_id=account.id)])
        for key, obj in zip(resources, (account, device, task, group, pair)):
            resources[key][name] = obj
    db.commit()
    yield dict(resources, users=users, client=TestClient(app), headers={
        name: {"Authorization": "Bearer " + create_access_token(u.id, u.username, u.role)} for name, u in users.items()
    })
    db.rollback()
    account_ids = [a.id for a in resources["accounts"].values()]
    device_ids = [d.id for d in resources["devices"].values()]
    group_ids = [g.id for g in resources["groups"].values()]
    for model, criterion in (
        (StatsEvent, StatsEvent.account_id.in_(account_ids)),
        (DailyStats, DailyStats.account_id.in_(account_ids)),
        (Task, Task.account_id.in_(account_ids)),
        (DevicePairRequest, DevicePairRequest.device_id.in_(device_ids)),
        (Device, Device.id.in_(device_ids)),
        (AccountGroupMember, AccountGroupMember.group_id.in_(group_ids)),
        (AccountGroup, AccountGroup.id.in_(group_ids)),
        (Account, Account.id.in_(account_ids)),
        (User, User.id.in_([u.id for u in users.values()])),
    ):
        db.query(model).filter(criterion).delete(synchronize_session=False)
    db.commit()


@pytest.mark.parametrize("method,suffix", [("get", ""), ("post", "/cancel"), ("delete", "")])
def test_other_user_cannot_access_task(identities, db, method, suffix):
    task = identities["tasks"]["owner"]
    response = getattr(identities["client"], method)(f"/api/tasks/{task.id}{suffix}", headers=identities["headers"]["other"])
    assert response.status_code in (403, 404)
    db.expire_all()
    assert db.get(Task, task.id).status == "pending"


@pytest.mark.parametrize("actor", ["owner", "admin"])
@pytest.mark.parametrize("method,suffix", [("get", ""), ("post", "/cancel"), ("delete", "")])
def test_owner_and_admin_can_manage_task(identities, actor, method, suffix):
    response = getattr(identities["client"], method)(f'/api/tasks/{identities["tasks"]["owner"].id}{suffix}', headers=identities["headers"][actor])
    assert response.status_code == 200


def test_mixed_bulk_delete_is_denied_without_partial_deletion(identities, db):
    ids = [t.id for t in identities["tasks"].values()]
    response = identities["client"].post("/api/tasks/batch-delete", json={"task_ids": ids}, headers=identities["headers"]["other"])
    assert response.status_code in (403, 404)
    assert db.query(Task).filter(Task.id.in_(ids)).count() == 2


@pytest.mark.parametrize("actor", ["owner", "admin"])
def test_owner_and_admin_bulk_delete(identities, actor):
    response = identities["client"].post("/api/tasks/batch-delete", json={"task_ids": [identities["tasks"]["owner"].id]}, headers=identities["headers"][actor])
    assert response.status_code == 200
    assert response.json() == {"deleted": 1}


@pytest.mark.parametrize("kind", ["account", "device", "batch_account", "batch_group"])
def test_create_rejects_foreign_resources(identities, db, kind):
    payload = {"type": "nurture", "params": {"duration": 30}}
    path = "/api/tasks"
    if kind == "account":
        payload["account_id"] = identities["accounts"]["owner"].id
    elif kind == "device":
        payload.update(account_id=identities["accounts"]["other"].id, device_id=identities["devices"]["owner"].id)
    else:
        path += "/batch"
        key, source = ("account_ids", "accounts") if kind == "batch_account" else ("group_ids", "groups")
        payload[key] = [identities[source]["owner"].id]
    response = identities["client"].post(path, json=payload, headers=identities["headers"]["other"])
    assert response.status_code in (403, 404)
    assert db.query(Task).filter(Task.account_id.in_([a.id for a in identities["accounts"].values()])).count() == 2


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_pair_action_cannot_rotate_or_reject_another_users_device(identities, db, action):
    device = identities["devices"]["owner"]
    original_secret = device.device_secret
    pair = identities["pairs"]["owner"]
    response = identities["client"].post(f"/api/devices/pair-requests/{pair.id}/{action}", headers=identities["headers"]["other"])
    assert response.status_code in (403, 404)
    db.expire_all()
    assert db.get(Device, device.id).device_secret == original_secret
    assert db.get(DevicePairRequest, pair.id).status == "pending"


@pytest.mark.parametrize("action", ["approve", "reject"])
@pytest.mark.parametrize("actor", ["owner", "admin"])
def test_owner_and_admin_can_handle_pair_request(identities, action, actor):
    response = identities["client"].post(f'/api/devices/pair-requests/{identities["pairs"]["owner"].id}/{action}', headers=identities["headers"][actor])
    assert response.status_code == 200


def test_pair_listing_does_not_disclose_another_users_request(identities):
    response = identities["client"].get("/api/devices/pair-requests", headers=identities["headers"]["other"])
    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["requests"]}
    assert identities["pairs"]["other"].id in ids
    assert identities["pairs"]["owner"].id not in ids


def test_device_cannot_bind_foreign_account(identities):
    response = identities["client"].put(f'/api/devices/{identities["devices"]["other"].id}', json={"bound_account_id": identities["accounts"]["owner"].id}, headers=identities["headers"]["other"])
    assert response.status_code in (403, 404)


class Socket:
    def __init__(self):
        self.messages = []
        self.ready = asyncio.Event()

    async def accept(self):
        pass

    async def send_json(self, data):
        self.messages.append(data)

    async def receive_text(self):
        self.ready.set()
        await asyncio.Future()


@pytest.mark.asyncio
async def test_websocket_route_delivers_scoped_events_to_owner_and_admin_only(monkeypatch):
    from app.routers import devices
    manager = PairWSManager()
    monkeypatch.setattr(devices, "pair_ws_manager", manager)
    sockets = {name: Socket() for name in ("owner", "other", "admin")}
    handlers = [asyncio.create_task(devices.ws_pair_events(ws, create_access_token(name, name, "admin" if name == "admin" else "operator"))) for name, ws in sockets.items()]
    try:
        await asyncio.gather(*(ws.ready.wait() for ws in sockets.values()))
        scoped = {"event": "task_progress", "task_id": "private-task"}
        await manager.broadcast_to_admins(scoped, user_ids=["owner"])
        assert sockets["owner"].messages == [scoped]
        assert sockets["admin"].messages == [scoped]
        assert sockets["other"].messages == []
        global_event = {"event": "new_pair_request"}
        await manager.broadcast_to_admins(global_event)
        assert sockets["owner"].messages == [scoped]
        assert sockets["other"].messages == []
        assert sockets["admin"].messages == [scoped, global_event]
    finally:
        for handler in handlers:
            handler.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)


@pytest.mark.parametrize("endpoint", ["progress", "report"])
def test_device_ownership_required_even_with_matching_lease(identities, endpoint):
    task = identities["tasks"]["owner"]
    payload = {"task_id": task.id, "lease_id": task.lease_id}
    payload.update({"step": "private", "detail": "private", "progress": 10} if endpoint == "progress" else {"status": "completed", "result": {}})
    response = identities["client"].post(f"/api/device/{endpoint}", json=payload, headers={"X-Device-Secret": identities["devices"]["other"].device_secret})
    assert response.status_code == 403


@pytest.mark.parametrize("endpoint", ["progress", "report"])
def test_task_updates_reach_owner_and_admin_only(identities, monkeypatch, endpoint):
    from app.routers import device, devices
    manager = PairWSManager()
    monkeypatch.setattr(device, "pair_ws_manager", manager)
    monkeypatch.setattr(devices, "pair_ws_manager", manager)
    sockets = {name: Socket() for name in ("owner", "other", "admin")}

    async def exercise():
        handlers = [asyncio.create_task(devices.ws_pair_events(ws, create_access_token(identities["users"][name].id, name, "admin" if name == "admin" else "operator"))) for name, ws in sockets.items()]
        try:
            await asyncio.gather(*(ws.ready.wait() for ws in sockets.values()))
            task = identities["tasks"]["owner"]
            payload = {"task_id": task.id, "lease_id": task.lease_id}
            payload.update({"step": "browse", "detail": "private", "progress": 10} if endpoint == "progress" else {"status": "completed", "result": {"private": True}})
            response = identities["client"].post(f"/api/device/{endpoint}", json=payload, headers={"X-Device-Secret": identities["devices"]["owner"].device_secret})
            assert response.status_code == 200
            expected = "task_progress" if endpoint == "progress" else "task_updated"
            assert any(m["event"] == expected for m in sockets["owner"].messages)
            assert any(m["event"] == expected for m in sockets["admin"].messages)
            assert sockets["other"].messages == []
        finally:
            for handler in handlers:
                handler.cancel()
            await asyncio.gather(*handlers, return_exceptions=True)

    asyncio.run(exercise())


@pytest.mark.asyncio
async def test_intentional_invalidation_is_global_and_payload_free():
    manager = PairWSManager()
    sockets = {name: Socket() for name in ("owner", "other", "admin")}
    for name, ws in sockets.items():
        await manager.register_admin(ws, name, role="admin" if name == "admin" else "operator")
    await manager.broadcast_invalidation("accounts_changed")
    assert all(ws.messages == [{"event": "accounts_changed"}] for ws in sockets.values())
    with pytest.raises(ValueError):
        await manager.broadcast_invalidation("task_progress")
    with pytest.raises(ValueError):
        await manager.broadcast_invalidation({"event": "accounts_changed", "secret": "private"})


def test_channel_management_refresh_reaches_owner_and_admin(identities, db, monkeypatch):
    from app.db_models import Channel
    from app.routers import channels, devices
    channel = Channel(group_id=identities["groups"]["owner"].id, task_type="nurture", user_id=identities["users"]["owner"].id)
    db.add(channel)
    db.commit()
    manager = PairWSManager()
    monkeypatch.setattr(channels, "pair_ws_manager", manager)
    monkeypatch.setattr(devices, "pair_ws_manager", manager)
    sockets = {name: Socket() for name in ("owner", "other", "admin")}

    async def exercise():
        handlers = [asyncio.create_task(devices.ws_pair_events(ws, create_access_token(identities["users"][name].id, name, "admin" if name == "admin" else "operator"))) for name, ws in sockets.items()]
        try:
            await asyncio.gather(*(ws.ready.wait() for ws in sockets.values()))
            response = identities["client"].patch(f"/api/channels/{channel.id}", json={"status": "paused"}, headers=identities["headers"]["admin"])
            assert response.status_code == 200
            assert sockets["owner"].messages == [{"event": "channels_changed"}]
            assert sockets["admin"].messages == [{"event": "channels_changed"}]
            assert sockets["other"].messages == []
        finally:
            for handler in handlers:
                handler.cancel()
            await asyncio.gather(*handlers, return_exceptions=True)

    try:
        asyncio.run(exercise())
    finally:
        db.query(Channel).filter(Channel.id == channel.id).delete(synchronize_session=False)
        db.commit()


@pytest.mark.parametrize("endpoint", ["progress", "report"])
@pytest.mark.parametrize("lease_cleared", [False, True])
def test_master_secret_cannot_apply_stale_attempt_report(identities, db, endpoint, lease_cleared):
    from app.config import DEVICE_SECRET
    task = identities["tasks"]["owner"]
    original_lease = task.lease_id
    task.lease_id = None if lease_cleared else "replacement-lease"
    task.device_id = None if lease_cleared else task.device_id
    task.status = "pending" if lease_cleared else "running"
    db.commit()
    original_status = task.status
    payload = {"task_id": task.id, "lease_id": original_lease}
    payload.update({"step": "old", "progress": 99} if endpoint == "progress" else {"status": "completed", "result": {"old": True}})
    response = identities["client"].post(f"/api/device/{endpoint}", json=payload, headers={"X-Device-Secret": DEVICE_SECRET})
    assert response.status_code == 200
    assert response.json().get("stale") is True
    db.expire_all()
    assert db.get(Task, task.id).status == original_status


@pytest.mark.parametrize("legacy", [False, True])
def test_stat_operation_restarts_per_lease_and_deduplicates_within_attempt(identities, db, legacy):
    task = identities["tasks"]["owner"]
    payload = {"task_id": task.id, "account_id": task.account_id, "task_type": "search_like", "target_id": "video", "op_index": 0, "count": 1}
    headers = {"X-Device-Secret": identities["devices"]["owner"].device_secret}
    leases = (task.lease_id, "new-attempt")
    for lease in leases:
        task.lease_id = lease
        db.commit()
        if not legacy:
            payload["lease_id"] = lease
        first = identities["client"].post("/api/device/stats/increment", json=payload, headers=headers)
        assert first.status_code == 200
        assert not first.json().get("duplicate")
        duplicate = identities["client"].post("/api/device/stats/increment", json=payload, headers=headers)
        assert duplicate.status_code == 200
        assert duplicate.json().get("duplicate") is True
    db.expire_all()
    assert db.query(DailyStats).filter_by(account_id=task.account_id).one().likes == 2
    events = db.query(StatsEvent).filter_by(task_id=task.id).all()
    assert len(events) == 2
    assert {event.lease_id for event in events} == set(leases)


@pytest.mark.parametrize("lease_cleared", [False, True])
def test_stale_stat_report_cannot_increment_after_attempt_changes(identities, db, lease_cleared):
    task = identities["tasks"]["owner"]
    stale_lease = task.lease_id
    task.lease_id = None if lease_cleared else "new-attempt"
    db.commit()
    response = identities["client"].post("/api/device/stats/increment", json={
        "task_id": task.id, "account_id": task.account_id, "task_type": "search_like",
        "lease_id": stale_lease, "target_id": "video", "op_index": 0,
    }, headers={"X-Device-Secret": identities["devices"]["owner"].device_secret})
    assert response.status_code == 200
    assert response.json().get("stale") is True
    assert db.query(StatsEvent).filter_by(task_id=task.id).count() == 0
    assert db.query(DailyStats).filter_by(account_id=task.account_id).count() == 0


def test_completed_attempt_accepts_delayed_stats_for_its_current_lease(identities, db):
    task = identities["tasks"]["owner"]
    task.status = "completed"
    db.commit()
    response = identities["client"].post("/api/device/stats/increment", json={
        "task_id": task.id, "account_id": task.account_id, "task_type": "search_like",
        "lease_id": task.lease_id, "target_id": "video", "op_index": 0,
    }, headers={"X-Device-Secret": identities["devices"]["owner"].device_secret})
    assert response.status_code == 200
    assert not response.json().get("stale")
    assert db.query(DailyStats).filter_by(account_id=task.account_id).one().likes == 1
