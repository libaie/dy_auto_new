"""Channel service tests."""
import pytest
from tests.conftest import setup_group
from app.db_models import Account, AccountGroup, AccountGroupMember, Channel, ChannelItem
from app.services.channel_service import channel_service


def test_create_channel_round_robin(db):
    setup_group(db, group_id="grp-cs-001", account_ids=["acc-cs-001", "acc-cs-002"])
    ch = channel_service.create_channel(
        db,
        group_id="grp-cs-001",
        task_type="search_comment",
        account_mode="round_robin",
        keywords=["美食", "旅游", "健身"],
        params_template={"content": "好棒", "count": 5},
    )
    assert ch.status == "active"
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).order_by(ChannelItem.queue_position).all()
    assert len(items) == 3
    # Round-robin should distribute across accounts
    account_ids = {i.account_id for i in items}
    assert len(account_ids) == 2  # both accounts used


def test_create_channel_single_account(db):
    setup_group(db, group_id="grp-cs-002", account_ids=["acc-cs-003", "acc-cs-004"])
    ch = channel_service.create_channel(
        db,
        group_id="grp-cs-002",
        task_type="search_like",
        account_mode="single_account",
        account_id="acc-cs-003",
        keywords=["a", "b"],
        params_template={"count": 10},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.account_id == "acc-cs-003" for i in items)


def test_create_channel_max_keywords_exceeded(db):
    setup_group(db, group_id="grp-cs-003", account_ids=["acc-cs-005"])
    with pytest.raises(ValueError, match="最多"):
        channel_service.create_channel(
            db,
            group_id="grp-cs-003",
            task_type="search_comment",
            account_mode="round_robin",
            keywords=["k"] * 501,
            params_template={},
        )


def test_create_channel_skips_non_active_accounts(db):
    """round_robin should skip risk_controlled/banned accounts."""
    group = AccountGroup(id="grp-cs-004", name="mixed")
    db.add(group)
    db.add(Account(id="acc-cs-active-1", nickname="active", status="active"))
    db.add(Account(id="acc-cs-risk-1", nickname="risk", status="risk_controlled"))
    db.add(AccountGroupMember(group_id="grp-cs-004", account_id="acc-cs-active-1"))
    db.add(AccountGroupMember(group_id="grp-cs-004", account_id="acc-cs-risk-1"))
    db.flush()

    ch = channel_service.create_channel(
        db,
        group_id="grp-cs-004",
        task_type="search_comment",
        account_mode="round_robin",
        keywords=["a", "b", "c"],
        params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.account_id == "acc-cs-active-1" for i in items)


def test_create_channel_invalid_group(db):
    """Should raise ValueError for non-existent group."""
    with pytest.raises(ValueError, match="不存在"):
        channel_service.create_channel(
            db, group_id="nonexistent", task_type="search_comment",
            account_mode="round_robin", keywords=["a"], params_template={},
        )


def test_create_channel_no_active_accounts(db):
    """Should raise ValueError when group has no active accounts."""
    group = AccountGroup(id="grp-cs-005", name="empty")
    db.add(group)
    db.add(Account(id="acc-cs-banned-1", nickname="banned", status="banned"))
    db.add(AccountGroupMember(group_id="grp-cs-005", account_id="acc-cs-banned-1"))
    db.flush()

    with pytest.raises(ValueError, match="活跃账号"):
        channel_service.create_channel(
            db, group_id="grp-cs-005", task_type="search_comment",
            account_mode="round_robin", keywords=["a"], params_template={},
        )


def test_create_channel_single_account_not_active(db):
    """Should raise ValueError when specified account is not active."""
    setup_group(db, group_id="grp-cs-006", account_ids=["acc-cs-006"])
    db.add(Account(id="acc-cs-risk-2", nickname="risk", status="risk_controlled"))
    db.add(AccountGroupMember(group_id="grp-cs-006", account_id="acc-cs-risk-2"))
    db.flush()

    with pytest.raises(ValueError, match="非 active"):
        channel_service.create_channel(
            db, group_id="grp-cs-006", task_type="search_comment",
            account_mode="single_account", account_id="acc-cs-risk-2",
            keywords=["a"], params_template={},
        )


def test_get_channel(db):
    setup_group(db, group_id="grp-cs-007", account_ids=["acc-cs-007"])
    ch = channel_service.create_channel(
        db, group_id="grp-cs-007", task_type="search_comment",
        account_mode="round_robin", keywords=["test"], params_template={},
    )
    found = channel_service.get_channel(db, ch.id)
    assert found is not None
    assert found.id == ch.id


def test_list_channels(db):
    setup_group(db, group_id="grp-cs-008", account_ids=["acc-cs-008"])
    channel_service.create_channel(
        db, group_id="grp-cs-008", task_type="search_comment",
        account_mode="round_robin", keywords=["a"], params_template={},
    )
    channels = channel_service.list_channels(db)
    assert len(channels) >= 1


def test_get_channel_stats(db):
    setup_group(db, group_id="grp-cs-009", account_ids=["acc-cs-009"])
    ch = channel_service.create_channel(
        db, group_id="grp-cs-009", task_type="search_comment",
        account_mode="round_robin", keywords=["a", "b"], params_template={},
    )
    stats = channel_service.get_channel_stats(db, ch.id)
    assert stats["total"] == 2
    assert stats["pending"] == 2
