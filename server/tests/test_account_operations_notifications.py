import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_account_mutation_broadcasts_accounts_changed():
    with patch("app.domains.account_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as broadcast:
        with TestClient(app) as client:
            response = client.post(
                "/api/accounts",
                json={"nickname": "notify-account", "douyin_id": _uid("notify")},
            )

    assert response.status_code == 200
    broadcast.assert_awaited_once_with({"event": "accounts_changed"})


def test_account_group_mutation_broadcasts_account_groups_changed():
    with patch("app.domains.account_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as broadcast:
        with TestClient(app) as client:
            response = client.post("/api/account-groups", json={"name": _uid("notify-group")})

    assert response.status_code == 200
    broadcast.assert_awaited_once_with({"event": "account_groups_changed"})


def test_channel_create_broadcasts_channels_changed(db):
    group_id = _uid("notify-grp")
    account_id = _uid("notify-acc")
    _seed_group(db, group_id, [account_id])

    with patch("app.domains.account_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as broadcast:
        with TestClient(app) as client:
            response = client.post(
                "/api/channels",
                json={
                    "group_id": group_id,
                    "task_type": "search_comment",
                    "account_mode": "single_account",
                    "account_id": account_id,
                    "keywords": ["notify-channel"],
                    "params_template": {},
                },
            )

    assert response.status_code == 200
    broadcast.assert_awaited_once_with({"event": "channels_changed"})


def test_channel_resume_broadcasts_channels_changed_and_new_task_available(db):
    group_id = _uid("notify-resume-grp")
    account_id = _uid("notify-resume-acc")
    _seed_group(db, group_id, [account_id])

    with TestClient(app) as client:
        created = client.post(
            "/api/channels",
            json={
                "group_id": group_id,
                "task_type": "search_comment",
                "account_mode": "single_account",
                "account_id": account_id,
                "keywords": ["notify-resume"],
                "params_template": {},
            },
        )
        channel_id = created.json()["id"]
        paused = client.patch(f"/api/channels/{channel_id}", json={"status": "paused"})

        with (
            patch("app.domains.account_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as admin_broadcast,
            patch("app.domains.account_operations.realtime_events.pair_ws_manager.broadcast_to_devices", new_callable=AsyncMock) as device_broadcast,
        ):
            response = client.patch(f"/api/channels/{channel_id}", json={"status": "active"})

    assert created.status_code == 200
    assert paused.status_code == 200
    assert response.status_code == 200
    admin_broadcast.assert_awaited_once_with({"event": "channels_changed"})
    device_broadcast.assert_awaited_once_with({"event": "new_task_available"})


def test_chain_template_mutation_broadcasts_chains_changed():
    with patch("app.routers.chains.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as broadcast:
        with TestClient(app) as client:
            response = client.post(
                "/api/chains/templates",
                json={
                    "name": _uid("notify-chain-template"),
                    "steps": [
                        {
                            "step_order": 1,
                            "type": "nurture",
                            "label": "warm",
                            "params": {"duration": 15},
                        }
                    ],
                },
            )

    assert response.status_code == 200
    broadcast.assert_awaited_once_with({"event": "chains_changed"})


def test_chain_cancel_broadcasts_chains_changed_and_sends_device_cancel(db):
    account_id = _uid("notify-chain-acc")
    device_id = _uid("notify-device")
    _seed_account(db, account_id)

    with TestClient(app) as client:
        template = client.post(
            "/api/chains/templates",
            json={
                "name": _uid("notify-chain-cancel"),
                "steps": [
                    {
                        "step_order": 1,
                        "type": "nurture",
                        "label": "warm",
                        "params": {"duration": 15},
                    }
                ],
            },
        )
        created = client.post(
            "/api/chains/instances",
            json={
                "template_id": template.json()["id"],
                "account_ids": [account_id],
                "device_id": device_id,
            },
        )
        instance_id = _latest_instance_id(db, account_id)

        with (
            patch("app.routers.chains.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as admin_broadcast,
            patch("app.routers.chains.pair_ws_manager.send_to_device", new_callable=AsyncMock) as send_to_device,
        ):
            response = client.post(f"/api/chains/instances/{instance_id}/cancel")

    assert template.status_code == 200
    assert created.status_code == 200
    assert response.status_code == 200
    admin_broadcast.assert_awaited_once_with({"event": "chains_changed"})
    send_to_device.assert_awaited_once()
    assert send_to_device.await_args.args[0] == device_id
    assert send_to_device.await_args.args[1]["event"] == "cancel_task"
    assert "task_id" in send_to_device.await_args.args[1]


def _uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _seed_account(db, account_id):
    from app.db_models import Account

    db.add(
        Account(
            id=account_id,
            nickname=account_id,
            douyin_id=f"dy-{account_id}",
            status="active",
            daily_limits={
                "likes": 50,
                "comments": 20,
                "follows": 20,
                "dms": 10,
                "replies": 15,
            },
        )
    )
    db.commit()


def _seed_group(db, group_id, account_ids):
    from app.db_models import AccountGroup, AccountGroupMember

    db.add(AccountGroup(id=group_id, name=group_id, description="notify group"))
    for account_id in account_ids:
        _seed_account(db, account_id)
        db.add(AccountGroupMember(group_id=group_id, account_id=account_id))
    db.commit()


def _latest_instance_id(db, account_id):
    from app.db_models import ChainInstance

    db.rollback()
    instance = (
        db.query(ChainInstance)
        .filter(ChainInstance.account_id == account_id)
        .order_by(ChainInstance.created_at.desc())
        .first()
    )
    assert instance is not None
    return instance.id
