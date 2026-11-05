"""Real lifecycle regressions, with SQLite foreign keys enforced."""
import asyncio
from datetime import timedelta
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import bj_now
from app.database import _set_sqlite_pragma
from app.db_models import Base, Account, Device, Task, AccountGroup, AccountGroupMember, ChannelItem, StatsEvent
from app.models import TaskType, TaskStatus
from app.services.channel_service import channel_service
from app.services.task_service import task_service
import app.main as main

@pytest.fixture
def life():
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool, connect_args={'check_same_thread': False})
    event.listen(engine, 'connect', _set_sqlite_pragma)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        db.add_all([Account(id=x, nickname=x, daily_limits={'comments': 20}) for x in ('a', 'b')])
        db.flush()
        db.add_all([Device(id=x, name=x, status='online', last_seen_at=bj_now()) for x in ('d', 'e')])
        db.commit()
        yield db, factory
    engine.dispose()

def channel(db, keywords=('one',), task_type='search_comment', params=None):
    db.add(AccountGroup(id='g', name='g')); db.flush()
    db.add(AccountGroupMember(group_id='g', account_id='a')); db.commit()
    return channel_service.create_channel(db, 'g', task_type, 'single_account', list(keywords), params or {}, account_id='a', cooldown_seconds=0)

def cycle(factory):
    sleeps = 0
    async def tick(_seconds):
        nonlocal sleeps
        sleeps += 1
        if sleeps > 1:
            raise asyncio.CancelledError()
    async def run():
        with patch.object(main, 'SessionLocal', factory), patch.object(main.asyncio, 'sleep', tick):
            try:
                await main._offline_checker()
            except asyncio.CancelledError:
                pass
    asyncio.run(run())

def test_pause_resume_keeps_pending_work(life):
    db, _ = life
    ch = channel(db, ('one', 'two'))
    channel_service.update_channel_status(db, ch.id, 'paused')
    assert [i.status for i in db.query(ChannelItem).all()] == ['pending', 'pending']
    assert channel_service.claim_channel_item(db, 'd') is None
    channel_service.update_channel_status(db, ch.id, 'active')
    assert channel_service.claim_channel_item(db, 'd') is not None

def test_pause_running_ack_survives_resume_and_late_ack(life):
    db, _ = life
    ch = channel(db)
    old, item_id = channel_service.claim_channel_item(db, 'd'); db.commit()
    channel_service.update_channel_status(db, ch.id, 'paused')
    channel_service.update_channel_status(db, ch.id, 'active')
    assert channel_service.claim_channel_item(db, 'e') is None
    task_service.report_result(db, old.id, TaskStatus.CANCELLED)
    replacement = channel_service.claim_channel_item(db, 'e')
    assert replacement is not None
    db.commit()
    task_service.report_result(db, old.id, TaskStatus.CANCELLED)
    db.expire_all()
    assert db.get(ChannelItem, item_id).task_id == replacement[0].id
    assert db.get(ChannelItem, item_id).status == 'assigned'

def test_healthy_30_minute_task_is_running_at_minute_11(life):
    db, factory = life
    task = task_service.create_task(db, TaskType.NURTURE, 'a', {'duration': 30})
    row = db.get(Task, task.id)
    row.status, row.device_id, row.started_at = 'running', 'd', bj_now() - timedelta(minutes=11)
    db.commit(); cycle(factory); db.expire_all()
    assert db.get(Task, task.id).status == 'running'
    assert db.get(Task, task.id).retry_count == 0

def test_checker_requeues_expired_direct_task_and_exhausts_budget(life):
    db, factory = life
    task = task_service.create_task(db, TaskType.SEARCH_COMMENT, 'a', {})
    for attempt in range(3):
        claimed = task_service.get_pending_task(db, 'd')
        assert claimed is not None and claimed.id == task.id
        db.get(Task, task.id).started_at = bj_now() - timedelta(minutes=11)
        db.commit(); cycle(factory); db.expire_all()
        assert db.get(Task, task.id).retry_count == attempt + 1
        assert db.get(Task, task.id).status == ('failed' if attempt == 2 else 'pending')

def test_direct_queue_claims_eligible_eleventh_task(life):
    db, _ = life
    db.get(Account, 'a').daily_limits = {'comments': 0}; db.commit()
    for i in range(10):
        task_service.create_task(db, TaskType.SEARCH_COMMENT, 'a', {'keyword': str(i)})
    eligible = task_service.create_task(db, TaskType.SEARCH_COMMENT, 'b', {})
    claimed = task_service.get_pending_task(db, 'd')
    assert claimed is not None and claimed.id == eligible.id

def test_direct_queue_skips_risk_controlled_account(life):
    db, _ = life
    db.get(Account, 'a').status = 'risk_controlled'; db.commit()
    task_service.create_task(db, TaskType.SEARCH_COMMENT, 'a', {})
    assert task_service.get_pending_task(db, 'd') is None

@pytest.mark.parametrize('batch', [False, True])
def test_task_hard_delete_removes_dependent_stats_events(life, batch):
    db, _ = life
    task = task_service.create_task(db, TaskType.SEARCH_COMMENT, 'a', {})
    db.get(Task, task.id).status = 'completed'
    db.add(StatsEvent(task_id=task.id, device_id='d', account_id='a', event_type='search_comment', target_id='x')); db.commit()
    assert (task_service.delete_tasks_batch(db, [task.id]) == 1 if batch else task_service.delete_task(db, task.id))
    assert db.get(Task, task.id) is None
    assert db.query(StatsEvent).count() == 0

def test_channel_stale_recovery_keeps_budget_across_replacement_tasks(life):
    db, _ = life
    ch = channel(db)
    history = []
    for attempt in range(5):
        claimed = channel_service.claim_channel_item(db, 'd'); db.commit()
        if claimed is None:
            history.append(None); continue
        task, item_id = claimed
        history.append(task.retry_count)
        old = bj_now() - timedelta(minutes=11)
        db.get(Task, task.id).started_at = old
        db.get(ChannelItem, item_id).assigned_at = old
        db.get(Device, 'd').last_seen_at = old; db.commit()
    assert history == [0, 1, 2, None, None]
    item = db.query(ChannelItem).filter_by(channel_id=ch.id).one()
    assert item.status == 'failed' and item.retry_count == 3
    assert db.query(Task).count() == 3

def test_offline_long_channel_task_not_reclaimed_before_deadline(life):
    db, _ = life
    channel(db, task_type='nurture', params={'duration': 30})
    task, item_id = channel_service.claim_channel_item(db, 'd')
    old = bj_now() - timedelta(minutes=11)
    db.get(Task, task.id).started_at = old
    db.get(ChannelItem, item_id).assigned_at = old
    db.get(Device, 'd').last_seen_at = old; db.commit()
    assert channel_service.claim_channel_item(db, 'e') is None
    assert db.get(ChannelItem, item_id).task_id == task.id

@pytest.mark.parametrize('params,minutes', [
    ({}, 32), ({'sub_tasks': []}, 62), ({'duration': '30'}, 32),
    ({'duration': 0}, 32), ({'duration': -2}, 32),
    ({'duration': float('inf')}, 32), ({'duration': True}, 32),
    ({'duration': 'bad', 'sub_tasks': []}, 62), ({'duration': 5}, 10),
])
def test_deadline_matches_nurture_duration_contract(params, minutes, monkeypatch):
    from app.services.task_deadline import task_timeout
    monkeypatch.setenv('TASK_STALE_MINUTES', '1')
    task = Task(type='nurture', params=params)
    assert task_timeout(task) == timedelta(minutes=minutes)


def test_configured_deadline_is_minimum_for_long_tasks(monkeypatch):
    from app.services.task_deadline import task_timeout
    monkeypatch.setenv('TASK_STALE_MINUTES', '45')
    assert task_timeout(Task(type='nurture', params={'duration': 30})) == timedelta(minutes=45)
    assert task_timeout(Task(type='nurture', params={'duration': 60})) == timedelta(minutes=62)


def test_orphan_failed_task_completes_channel_instead_of_resurrecting(life):
    db, _ = life
    ch = channel(db)
    task, item_id = channel_service.claim_channel_item(db, 'd')
    db.get(Task, task.id).status = 'failed'
    db.commit()
    assert channel_service.claim_channel_item(db, 'e') is None
    db.refresh(ch)
    assert db.get(ChannelItem, item_id).status == 'failed'
    assert ch.status == 'completed'


def test_mixed_channel_failures_and_timeouts_share_one_budget(life):
    db, factory = life
    ch = channel(db)
    first, item_id = channel_service.claim_channel_item(db, 'd'); db.commit()
    task_service.report_result(db, first.id, TaskStatus.FAILED)
    second, _ = channel_service.claim_channel_item(db, 'd'); db.commit()
    assert second.retry_count == 1
    old = bj_now() - timedelta(minutes=11)
    db.get(Task, second.id).started_at = old
    db.get(Device, 'd').last_seen_at = old
    db.commit(); cycle(factory); db.expire_all()
    third, _ = channel_service.claim_channel_item(db, 'e'); db.commit()
    assert third.retry_count == 2
    task_service.report_result(db, third.id, TaskStatus.FAILED)
    assert db.get(ChannelItem, item_id).retry_count == 3
    assert db.get(ChannelItem, item_id).status == 'failed'
    assert channel_service.claim_channel_item(db, 'd') is None


def test_late_pause_ack_after_grace_cannot_reset_replacement(life):
    db, _ = life
    ch = channel(db)
    old, item_id = channel_service.claim_channel_item(db, 'd'); db.commit()
    channel_service.update_channel_status(db, ch.id, 'paused')
    channel_service.update_channel_status(db, ch.id, 'active')
    db.get(Task, old.id).completed_at = bj_now() - timedelta(minutes=6)
    db.commit()
    replacement = channel_service.claim_channel_item(db, 'e')
    assert replacement is not None
    db.commit()
    task_service.report_result(db, old.id, TaskStatus.CANCELLED)
    db.expire_all()
    assert db.get(ChannelItem, item_id).task_id == replacement[0].id
    assert db.get(ChannelItem, item_id).status == 'assigned'
    assert db.get(Task, old.id).device_id is None


def test_timeout_exhaustion_marks_actual_chain_failed(life):
    from app.db_models import ChainTemplate, ChainInstance
    from app.services.chain_service import chain_service
    db, factory = life
    template = ChainTemplate(name='timeout-chain', steps=[
        {'step_order': 1, 'type': 'search_comment', 'params': {}},
        {'step_order': 2, 'type': 'search_like', 'params': {}},
    ])
    db.add(template)
    db.commit()
    created = chain_service.create_chain_instances(db, template.id, ['a'])
    assert created['created'] == ['a']
    chain = db.query(ChainInstance).one()
    task = db.query(Task).filter_by(chain_instance_id=chain.id).one()
    for attempt in range(3):
        claimed = task_service.get_pending_task(db, 'd')
        assert claimed is not None and claimed.id == task.id
        db.get(Task, task.id).started_at = bj_now() - timedelta(minutes=11)
        db.commit()
        cycle(factory)
        db.expire_all()
        assert db.get(Task, task.id).retry_count == attempt + 1
        current_chain = db.get(ChainInstance, chain.id)
        assert current_chain.status == ('failed' if attempt == 2 else 'running')
    assert current_chain.completed_at is not None
    assert current_chain.current_step == 1
    assert db.query(Task).filter_by(chain_instance_id=chain.id).count() == 1
    assert task_service.get_pending_task(db, 'e') is None
