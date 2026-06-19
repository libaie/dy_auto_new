import uuid

from fastapi.testclient import TestClient

from app.main import app


ACCOUNT_KEYS = {"id", "nickname", "douyin_id", "group", "status", "daily_limits", "created_at", "updated_at"}
GROUP_KEYS = {"id", "name", "description", "member_count", "created_at", "updated_at"}
MEMBER_KEYS = {"id", "nickname", "douyin_id", "status"}
CHANNEL_KEYS = {
    "id",
    "group_id",
    "group_name",
    "task_type",
    "status",
    "account_mode",
    "account_id",
    "params_template",
    "cooldown_seconds",
    "delay_range",
    "total",
    "pending",
    "assigned",
    "completed",
    "failed",
    "skipped",
    "created_at",
    "completed_at",
}
CHANNEL_ITEM_KEYS = {
    "id",
    "keyword",
    "account_id",
    "account_nickname",
    "status",
    "assigned_device_id",
    "device_name",
    "task_id",
    "queue_position",
    "created_at",
    "completed_at",
}
CHAIN_TEMPLATE_KEYS = {"id", "name", "description", "steps", "created_at", "updated_at"}
CHAIN_INSTANCE_KEYS = {
    "id",
    "template_id",
    "template_name",
    "account_id",
    "account_nickname",
    "device_id",
    "device_name",
    "current_step",
    "total_steps",
    "status",
    "created_at",
    "started_at",
    "completed_at",
}
CHAIN_TASK_KEYS = {"id", "step_order", "type", "status", "params", "result", "started_at", "completed_at"}


def test_read_model_module_owns_account_group_channel_and_chain_payload_helpers():
    import app.domains.account_operations.read_models as read_models

    for name in (
        "account_to_dict",
        "group_to_dict",
        "member_to_dict",
        "channel_to_response",
        "channel_item_to_response",
        "chain_template_to_dict",
        "chain_instance_to_dict",
    ):
        assert hasattr(read_models, name)


def test_account_list_response_shape():
    with TestClient(app) as client:
        created = client.post(
            "/api/accounts",
            json={
                "nickname": "account-read-model",
                "douyin_id": _uid("douyin"),
                "group": "read-model",
            },
        )
        response = client.get("/api/accounts")

    assert created.status_code == 200
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"accounts", "total"}
    assert data["total"] >= 1
    account = next(item for item in data["accounts"] if item["id"] == created.json()["id"])
    assert set(account) == ACCOUNT_KEYS


def test_group_and_member_response_shapes():
    with TestClient(app) as client:
        account = client.post(
            "/api/accounts",
            json={"nickname": "member-read-model", "douyin_id": _uid("member")},
        )
        group = client.post(
            "/api/account-groups",
            json={"name": _uid("group"), "description": "read model group"},
        )
        added = client.post(
            f"/api/account-groups/{group.json()['id']}/members",
            json={"account_ids": [account.json()["id"]]},
        )
        listed = client.get("/api/account-groups")
        members = client.get(f"/api/account-groups/{group.json()['id']}/members")

    assert account.status_code == 200
    assert group.status_code == 200
    assert added.status_code == 200

    assert listed.status_code == 200
    assert set(listed.json()) == {"groups", "total"}
    assert set(listed.json()["groups"][0]) == GROUP_KEYS

    assert members.status_code == 200
    assert set(members.json()) == {"members", "total"}
    assert members.json()["total"] == 1
    assert set(members.json()["members"][0]) == MEMBER_KEYS


def test_channel_list_detail_and_item_response_shapes(db):
    group_id = _uid("grp")
    account_id = _uid("acc")
    _seed_group(db, group_id, [account_id])

    with TestClient(app) as client:
        created = client.post(
            "/api/channels",
            json={
                "group_id": group_id,
                "task_type": "search_comment",
                "account_mode": "single_account",
                "account_id": account_id,
                "keywords": ["read-model-channel"],
                "params_template": {"content": "hello"},
            },
        )
        listed = client.get("/api/channels")
        detail = client.get(f"/api/channels/{created.json()['id']}")

    assert created.status_code == 200
    assert set(created.json()) == CHANNEL_KEYS

    assert listed.status_code == 200
    assert set(listed.json()) == {"channels", "total"}
    listed_channel = next(channel for channel in listed.json()["channels"] if channel["id"] == created.json()["id"])
    assert set(listed_channel) == CHANNEL_KEYS

    assert detail.status_code == 200
    assert set(detail.json()) == CHANNEL_KEYS | {"items"}
    assert len(detail.json()["items"]) == 1
    assert set(detail.json()["items"][0]) == CHANNEL_ITEM_KEYS


def test_chain_template_instance_and_task_response_shapes(db):
    account_id = _uid("acc-chain")
    _seed_account(db, account_id)

    with TestClient(app) as client:
        template = client.post(
            "/api/chains/templates",
            json={
                "name": _uid("chain-template"),
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
        templates = client.get("/api/chains/templates")
        created_instances = client.post(
            "/api/chains/instances",
            json={"template_id": template.json()["id"], "account_ids": [account_id]},
        )
        instances = client.get("/api/chains/instances")
        instance = next(item for item in instances.json()["instances"] if item["account_id"] == account_id)
        detail = client.get(f"/api/chains/instances/{instance['id']}")

    assert template.status_code == 200
    assert set(template.json()) == CHAIN_TEMPLATE_KEYS
    assert template.json()["steps"][0]["step_order"] == 1

    assert templates.status_code == 200
    assert set(templates.json()) == {"templates", "total"}
    assert set(templates.json()["templates"][0]) == CHAIN_TEMPLATE_KEYS

    assert created_instances.status_code == 200
    assert created_instances.json()["created_count"] == 1

    assert instances.status_code == 200
    assert set(instances.json()) == {"instances", "total"}
    assert set(instance) == CHAIN_INSTANCE_KEYS

    assert detail.status_code == 200
    assert set(detail.json()) == CHAIN_INSTANCE_KEYS | {"tasks"}
    assert len(detail.json()["tasks"]) == 1
    assert set(detail.json()["tasks"][0]) == CHAIN_TASK_KEYS


def _uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _seed_account(db, account_id, nickname=None):
    from app.db_models import Account

    db.add(
        Account(
            id=account_id,
            nickname=nickname or account_id,
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

    db.add(AccountGroup(id=group_id, name=group_id, description="read model group"))
    for account_id in account_ids:
        _seed_account(db, account_id)
        db.add(AccountGroupMember(group_id=group_id, account_id=account_id))
    db.commit()
