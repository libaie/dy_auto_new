"""Channel and ChannelItem ORM model tests."""
import pytest
from tests.conftest import setup_group
from app.db.models import Channel, ChannelItem


def test_create_channel(db):
    group = setup_group(db, group_id="grp-ch-001", account_ids=["a1", "a2"])
    ch = Channel(
        id="ch-001",
        group_id=group.id,
        task_type="search_comment",
        status="active",
        account_mode="round_robin",
        params_template={"content": "hi", "count": 5},
        cooldown_seconds=300,
        delay_range=[3000, 8000],
        max_keywords=500,
    )
    db.add(ch)
    db.flush()
    assert ch.id == "ch-001"
    assert ch.status == "active"
    assert ch.deleted_at is None


def test_create_channel_item(db):
    group = setup_group(db, group_id="grp-ch-002", account_ids=["a1"])
    ch = Channel(id="ch-002", group_id=group.id, task_type="search_like",
                 status="active", account_mode="single_account", account_id="a1",
                 params_template={"count": 10})
    db.add(ch)
    item = ChannelItem(
        id="ci-001",
        channel_id="ch-002",
        keyword="美食",
        account_id="a1",
        status="pending",
        queue_position=0,
    )
    db.add(item)
    db.flush()
    assert item.status == "pending"
    assert item.assigned_device_id is None
    assert item.task_id is None


def test_channel_item_indexes(db):
    """Verify composite index exists on (channel_id, status)."""
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(db.bind)
    indexes = {idx["name"] for idx in insp.get_indexes("channel_items")}
    assert "ix_channel_items_channel_status" in indexes
