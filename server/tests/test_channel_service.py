"""Channel service tests."""
import pytest
from datetime import datetime, timezone
from tests.conftest import setup_group
from app.db.models import Account, AccountGroup, AccountGroupMember, Channel, ChannelItem
from app.domains.account_operations.channel_service import channel_service


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


def test_claim_pending_item(db):
    """Device should be able to claim a pending channel item."""
    setup_group(db, group_id="grp-cl-001", account_ids=["acc-cl-001"])
    ch = channel_service.create_channel(
        db, group_id="grp-cl-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-cl-001",
        keywords=["美食"], params_template={"content": "hi", "count": 5},
    )
    from app.db.models import Device
    db.add(Device(id="dev-cl-001", name="test-device", status="online"))
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-cl-001")
    assert result is not None
    task, channel_item_id = result
    assert task.type == "search_comment"
    assert task.account_id == "acc-cl-001"

    item = db.query(ChannelItem).filter(ChannelItem.id == channel_item_id).first()
    assert item.status == "assigned"
    assert item.assigned_device_id == "dev-cl-001"
    assert item.task_id == task.id


def test_claim_respects_account_status_filter(db):
    """Should not claim items for risk_controlled accounts."""
    group = AccountGroup(id="grp-cl-002", name="risk-group")
    db.add(group)
    db.add(Account(id="acc-cl-risk", nickname="risk", status="risk_controlled"))
    db.add(AccountGroupMember(group_id="grp-cl-002", account_id="acc-cl-risk"))
    db.flush()

    ch = Channel(id="ch-cl-risk", group_id="grp-cl-002", task_type="search_comment",
                 status="active", account_mode="single_account", account_id="acc-cl-risk",
                 params_template={})
    db.add(ch)
    db.add(ChannelItem(id="ci-cl-risk", channel_id="ch-cl-risk", keyword="test",
                       account_id="acc-cl-risk", status="pending", queue_position=0))
    db.flush()

    from app.db.models import Device
    db.add(Device(id="dev-cl-risk", name="dev", status="online"))
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-cl-risk")
    assert result is None


def test_claim_respects_per_account_concurrency(db):
    """Should not assign second item to account that already has running channel task."""
    setup_group(db, group_id="grp-cl-003", account_ids=["acc-cl-003"])
    ch = channel_service.create_channel(
        db, group_id="grp-cl-003", task_type="search_comment",
        account_mode="single_account", account_id="acc-cl-003",
        keywords=["a", "b"], params_template={"content": "x", "count": 1},
    )
    from app.db.models import Device
    db.add(Device(id="dev-cl-c1", name="c1", status="online"))
    db.add(Device(id="dev-cl-c2", name="c2", status="online"))
    db.flush()

    result1 = channel_service.claim_channel_item(db, "dev-cl-c1")
    assert result1 is not None

    result2 = channel_service.claim_channel_item(db, "dev-cl-c2")
    assert result2 is None


def test_claim_returns_none_when_empty(db):
    """Should return None when no pending items."""
    from app.db.models import Device
    db.add(Device(id="dev-cl-empty", name="empty", status="online"))
    db.flush()
    result = channel_service.claim_channel_item(db, "dev-cl-empty")
    assert result is None


def test_claim_stale_recovery(db):
    """Items assigned > 10 min ago should auto-revert to pending."""
    from datetime import timedelta
    setup_group(db, group_id="grp-cl-004", account_ids=["acc-cl-004"])
    ch = channel_service.create_channel(
        db, group_id="grp-cl-004", task_type="search_comment",
        account_mode="single_account", account_id="acc-cl-004",
        keywords=["stale-kw"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    item = items[0]
    from app.db.models import Device
    db.add(Device(id="dev-cl-stale", name="stale", status="online"))
    db.flush()
    item.status = "assigned"
    item.assigned_device_id = "dev-cl-stale"
    item.assigned_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=11)
    db.flush()

    db.add(Device(id="dev-cl-new", name="new", status="online"))
    db.flush()
    result = channel_service.claim_channel_item(db, "dev-cl-new")
    assert result is not None

    db.refresh(item)
    assert item.status == "assigned"
    assert item.assigned_device_id == "dev-cl-new"


def test_claim_cooldown_filtering(db):
    """Should not claim item if account is within cooldown period."""
    setup_group(db, group_id="grp-cl-005", account_ids=["acc-cl-005"])
    ch = channel_service.create_channel(
        db, group_id="grp-cl-005", task_type="search_comment",
        account_mode="single_account", account_id="acc-cl-005",
        keywords=["cd-a", "cd-b"], params_template={},
        cooldown_seconds=600,
    )
    from app.db.models import Device
    db.add(Device(id="dev-cl-cd1", name="cd1", status="online"))
    db.add(Device(id="dev-cl-cd2", name="cd2", status="online"))
    db.flush()

    result1 = channel_service.claim_channel_item(db, "dev-cl-cd1")
    assert result1 is not None

    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).order_by(ChannelItem.queue_position).all()
    items[0].status = "completed"
    items[0].completed_at = datetime.now(timezone.utc)
    db.flush()

    result2 = channel_service.claim_channel_item(db, "dev-cl-cd2")
    assert result2 is None


def test_claim_respects_bound_account_routing(db):
    """Bound device should only claim items for its bound account."""
    group = AccountGroup(id="grp-cl-006", name="bound-group")
    db.add(group)
    db.add(Account(id="acc-cl-b1", nickname="b1", status="active"))
    db.add(Account(id="acc-cl-b2", nickname="b2", status="active"))
    db.add(AccountGroupMember(group_id="grp-cl-006", account_id="acc-cl-b1"))
    db.add(AccountGroupMember(group_id="grp-cl-006", account_id="acc-cl-b2"))
    db.flush()

    ch = Channel(id="ch-cl-bound", group_id="grp-cl-006", task_type="search_comment",
                 status="active", account_mode="round_robin", params_template={})
    db.add(ch)
    db.add(ChannelItem(id="ci-cl-b1", channel_id="ch-cl-bound", keyword="kw1",
                       account_id="acc-cl-b1", status="pending", queue_position=0))
    db.add(ChannelItem(id="ci-cl-b2", channel_id="ch-cl-bound", keyword="kw2",
                       account_id="acc-cl-b2", status="pending", queue_position=1))
    db.flush()

    from app.db.models import Device
    db.add(Device(id="dev-cl-bound", name="bound", status="online", bound_account_id="acc-cl-b1"))
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-cl-bound")
    assert result is not None
    task, item_id = result
    assert task.account_id == "acc-cl-b1"


def test_claim_concurrent_optimistic_lock(db):
    """Two devices trying to claim the same item — only one succeeds."""
    setup_group(db, group_id="grp-cl-007", account_ids=["acc-cl-007"])
    ch = channel_service.create_channel(
        db, group_id="grp-cl-007", task_type="search_comment",
        account_mode="single_account", account_id="acc-cl-007",
        keywords=["concurrent"], params_template={},
    )
    from app.db.models import Device
    db.add(Device(id="dev-cl-oc1", name="c1", status="online"))
    db.add(Device(id="dev-cl-oc2", name="c2", status="online"))
    db.flush()

    result1 = channel_service.claim_channel_item(db, "dev-cl-oc1")
    result2 = channel_service.claim_channel_item(db, "dev-cl-oc2")
    assert result1 is not None
    assert result2 is None


def test_claim_respects_quota_limit(db):
    """Should not claim item if account has exceeded daily quota."""
    from app.domains.reporting.stats_service import stats_service
    setup_group(db, group_id="grp-cl-008", account_ids=["acc-cl-008"])
    ch = channel_service.create_channel(
        db, group_id="grp-cl-008", task_type="search_comment",
        account_mode="single_account", account_id="acc-cl-008",
        keywords=["quota-kw"], params_template={},
    )
    from app.db.models import Device
    db.add(Device(id="dev-cl-quota", name="quota", status="online"))
    db.flush()

    for _ in range(20):
        stats_service.increment(db, "acc-cl-008", "search_comment")
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-cl-quota")
    assert result is None


def test_claim_nurture_injects_item_keyword_matrix(db):
    setup_group(db, group_id="grp-cl-nurture-matrix", account_ids=["acc-cl-nurture-matrix"])
    ch = channel_service.create_channel(
        db,
        group_id="grp-cl-nurture-matrix",
        task_type="nurture",
        account_mode="single_account",
        account_id="acc-cl-nurture-matrix",
        keywords=["diet-keyword"],
        params_template={
            "sub_tasks": [{"type": "like", "count": 1}],
            "keyword_matrix": ["health-keyword"],
            "duration": 10,
        },
    )
    from app.db.models import Device
    db.add(Device(id="dev-cl-nurture-matrix", name="dev", status="online"))
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-cl-nurture-matrix")

    assert result is not None
    task, _ = result
    assert task.params["keyword"] == "diet-keyword"
    assert task.params["keyword_matrix"] == ["diet-keyword", "health-keyword"]


def test_claim_nurture_respects_comment_quota(db):
    from app.domains.reporting.stats_service import stats_service
    setup_group(db, group_id="grp-cl-nurture-quota", account_ids=["acc-cl-nurture-quota"])
    account = db.query(Account).filter(Account.id == "acc-cl-nurture-quota").first()
    account.daily_limits = {
        "comments": 1,
        "follows": 20,
        "likes": 50,
        "nurture_likes": 200,
    }
    db.flush()
    stats_service.increment(db, "acc-cl-nurture-quota", "search_comment", count=1)
    ch = channel_service.create_channel(
        db,
        group_id="grp-cl-nurture-quota",
        task_type="nurture",
        account_mode="single_account",
        account_id="acc-cl-nurture-quota",
        keywords=["quota-keyword"],
        params_template={
            "sub_tasks": [{"type": "comment", "count": 1}],
            "duration": 10,
        },
    )
    from app.db.models import Device
    db.add(Device(id="dev-cl-nurture-quota", name="dev", status="online"))
    db.flush()

    result = channel_service.claim_channel_item(db, "dev-cl-nurture-quota")

    assert result is None


def test_complete_item_marks_channel_completed_when_all_done(db):
    """Channel should be marked completed when all items are terminal."""
    setup_group(db, group_id="grp-cm-001", account_ids=["acc-cm-001"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-001", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-001",
        keywords=["only-one"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert len(items) == 1

    channel_service.complete_item(db, items[0].id, "completed")

    db.refresh(ch)
    assert ch.status == "completed"
    assert ch.completed_at is not None


def test_complete_item_not_completed_when_items_remain(db):
    """Channel should stay active when items remain."""
    setup_group(db, group_id="grp-cm-002", account_ids=["acc-cm-002"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-002", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-002",
        keywords=["a", "b"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).order_by(ChannelItem.queue_position).all()

    channel_service.complete_item(db, items[0].id, "completed")

    db.refresh(ch)
    assert ch.status == "active"


def test_complete_item_failed_marks_failed(db):
    """Channel task failure marks item as failed (no retry rollback)."""
    setup_group(db, group_id="grp-cm-003", account_ids=["acc-cm-003"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-003", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-003",
        keywords=["fail-kw"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    item = items[0]
    item.status = "assigned"
    item.assigned_device_id = "dev-cm-001"
    db.flush()

    result = channel_service.complete_item(db, item.id, "failed")

    db.refresh(item)
    assert item.status == "failed"
    assert item.completed_at is not None
    assert result["channel_id"] == ch.id
    assert result["channel_completed"] is True  # only 1 item, all done


def test_risk_control_skips_pending_items(db):
    """Risk control event should skip all pending items for the account."""
    setup_group(db, group_id="grp-cm-004", account_ids=["acc-cm-004"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-004", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-004",
        keywords=["a", "b", "c"], params_template={},
    )

    channel_service.on_risk_control(db, "acc-cm-004")

    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.status == "skipped" for i in items)


def test_cancel_channel_skips_pending_items(db):
    """Cancelling a channel should skip all pending items."""
    setup_group(db, group_id="grp-cm-005", account_ids=["acc-cm-005"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-005", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-005",
        keywords=["x", "y"], params_template={},
    )

    channel_service.update_channel_status(db, ch.id, "cancelled")

    db.refresh(ch)
    assert ch.status == "cancelled"
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.status == "skipped" for i in items)


def test_pause_and_resume_channel(db):
    """Pause and resume a channel."""
    setup_group(db, group_id="grp-cm-006", account_ids=["acc-cm-006"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-006", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-006",
        keywords=["pause-kw"], params_template={},
    )

    channel_service.update_channel_status(db, ch.id, "paused")
    db.refresh(ch)
    assert ch.status == "paused"

    channel_service.update_channel_status(db, ch.id, "active")
    db.refresh(ch)
    assert ch.status == "active"


def test_invalid_status_transition(db):
    """Should raise ValueError for invalid status transitions."""
    setup_group(db, group_id="grp-cm-007", account_ids=["acc-cm-007"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-007", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-007",
        keywords=["inv-kw"], params_template={},
    )

    with pytest.raises(ValueError, match="不允许"):
        channel_service.update_channel_status(db, ch.id, "completed")


def test_soft_delete_channel(db):
    """Soft delete should set deleted_at and skip pending items."""
    setup_group(db, group_id="grp-cm-008", account_ids=["acc-cm-008"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-008", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-008",
        keywords=["del-a", "del-b"], params_template={},
    )

    channel_service.soft_delete_channel(db, ch.id)

    db.refresh(ch)
    assert ch.deleted_at is not None
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    assert all(i.status == "skipped" for i in items)


def test_append_items_to_active_channel(db):
    """Should append new keywords to an active channel."""
    setup_group(db, group_id="grp-cm-009", account_ids=["acc-cm-009"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-009", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-009",
        keywords=["orig"], params_template={},
    )

    channel_service.append_items(db, ch.id, ["new-a", "new-b"])

    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).order_by(ChannelItem.queue_position).all()
    assert len(items) == 3
    assert items[1].keyword == "new-a"
    assert items[2].keyword == "new-b"


def test_append_items_rejects_paused_channel(db):
    """Should raise ValueError when appending to a paused channel."""
    setup_group(db, group_id="grp-cm-010", account_ids=["acc-cm-010"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-010", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-010",
        keywords=["orig"], params_template={},
    )
    channel_service.update_channel_status(db, ch.id, "paused")

    with pytest.raises(ValueError, match="活跃"):
        channel_service.append_items(db, ch.id, ["new"])


def test_update_item_status_skip(db):
    """Should allow skipping a pending item."""
    setup_group(db, group_id="grp-cm-011", account_ids=["acc-cm-011"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-011", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-011",
        keywords=["skip-kw"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()

    channel_service.update_item_status(db, items[0].id, "skipped")
    db.refresh(items[0])
    assert items[0].status == "skipped"


def test_update_item_status_requeue_failed(db):
    """Should allow re-queuing a failed item."""
    setup_group(db, group_id="grp-cm-012", account_ids=["acc-cm-012"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-012", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-012",
        keywords=["requeue-kw"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()
    items[0].status = "failed"
    items[0].completed_at = datetime.now(timezone.utc)
    db.flush()

    channel_service.update_item_status(db, items[0].id, "pending")
    db.refresh(items[0])
    assert items[0].status == "pending"
    assert items[0].completed_at is None


def test_complete_item_failed_finalizes_channel(db):
    """Failed items (no retry) should contribute to channel completion."""
    setup_group(db, group_id="grp-cm-013", account_ids=["acc-cm-013"])
    ch = channel_service.create_channel(
        db, group_id="grp-cm-013", task_type="search_comment",
        account_mode="single_account", account_id="acc-cm-013",
        keywords=["fail-final"], params_template={},
    )
    items = db.query(ChannelItem).filter(ChannelItem.channel_id == ch.id).all()

    channel_service.complete_item(db, items[0].id, "failed")

    db.refresh(ch)
    assert ch.status == "completed"
