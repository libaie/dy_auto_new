import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class FakePairWsManager:
    def __init__(self, heartbeats=None):
        self._heartbeats = dict(heartbeats or {})
        self._device_last_seen = {}
        self.broadcasts = []
        self.drain_calls = 0

    def drain_heartbeats(self):
        self.drain_calls += 1
        heartbeats = dict(self._heartbeats)
        self._heartbeats.clear()
        return heartbeats

    async def broadcast_to_admins(self, payload):
        self.broadcasts.append(payload)


class FakeSession:
    def __init__(self, first_devices=None, online_devices=None, stuck_tasks=None, fail_commits=0):
        self.first_devices = list(first_devices or [])
        self.online_devices = list(online_devices or [])
        self.stuck_tasks = list(stuck_tasks or [])
        self.fail_commits = fail_commits
        self.commit_count = 0
        self.closed = False
        self.queries = []
        self.updates = []
        self.channel_updates = []

    def query(self, model):
        model_name = getattr(model, "__name__", str(model))
        self.queries.append(model_name)
        return FakeQuery(self, model_name)

    def commit(self):
        self.commit_count += 1
        if self.fail_commits:
            self.fail_commits -= 1
            raise RuntimeError("commit failed")

    def close(self):
        self.closed = True


class FakeQuery:
    def __init__(self, session, model_name):
        self.session = session
        self.model_name = model_name
        self.conditions = []

    def filter(self, *conditions):
        self.conditions.extend(conditions)
        return self

    def first(self):
        if self.model_name == "Device" and self.session.first_devices:
            return self.session.first_devices.pop(0)
        return None

    def all(self):
        if self.model_name == "Device":
            return list(self.session.online_devices)
        if self.model_name == "Task":
            return list(self.session.stuck_tasks)
        return []

    def update(self, values, synchronize_session=False):
        self.session.updates.append((self.model_name, dict(values), synchronize_session))
        if self.model_name == "Device":
            for device in self.session.online_devices:
                for key, value in values.items():
                    setattr(device, key, value)
        if self.model_name == "ChannelItem":
            self.session.channel_updates.append(dict(values))
        return 1


@pytest.mark.asyncio
async def test_offline_checker_requeues_drained_heartbeats_when_flush_commit_fails(monkeypatch):
    now = datetime(2026, 6, 19, 9, 0, 0)
    seen_at = now - timedelta(seconds=3)
    device = SimpleNamespace(id="device-1", status="offline", last_seen_at=None)
    session = FakeSession(first_devices=[device], online_devices=[], fail_commits=1)
    manager = FakePairWsManager(heartbeats={"device-1": seen_at})

    await _run_offline_checker_one_cycle(monkeypatch, session, manager, now)

    assert manager.drain_calls == 1
    assert manager._device_last_seen == {"device-1": seen_at}
    assert device.last_seen_at == seen_at
    assert device.status == "online"
    assert session.commit_count == 1
    assert session.closed is True


@pytest.mark.asyncio
async def test_offline_checker_marks_stale_devices_offline_and_broadcasts_current_payload(monkeypatch):
    now = datetime(2026, 6, 19, 9, 0, 0)
    stale_device = SimpleNamespace(
        id="device-stale",
        status="online",
        last_seen_at=now - timedelta(seconds=121),
    )
    session = FakeSession(online_devices=[stale_device])
    manager = FakePairWsManager()

    await _run_offline_checker_one_cycle(monkeypatch, session, manager, now)

    assert ("Device", {"status": "offline"}, False) in session.updates
    assert stale_device.status == "offline"
    assert manager.broadcasts == [
        {
            "event": "device_status_changed",
            "device_id": "device-stale",
            "status": "offline",
        }
    ]
    assert session.closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initial_retry_count", "expected_task_status", "expected_channel_status"),
    [
        (0, "cancelled", "pending"),
        ("max_minus_one", "failed", "failed"),
    ],
)
async def test_offline_checker_handles_stuck_online_device_tasks(
    monkeypatch,
    initial_retry_count,
    expected_task_status,
    expected_channel_status,
):
    from app.services.task_service import MAX_RETRIES

    now = datetime(2026, 6, 19, 9, 0, 0)
    retry_count = MAX_RETRIES - 1 if initial_retry_count == "max_minus_one" else initial_retry_count
    online_device = SimpleNamespace(id="device-online", status="online", last_seen_at=now)
    stuck_task = SimpleNamespace(
        id="task-1",
        status="running",
        retry_count=retry_count,
        completed_at=None,
        device_id="device-online",
        started_at=now - timedelta(minutes=11),
    )
    session = FakeSession(online_devices=[online_device], stuck_tasks=[stuck_task])
    manager = FakePairWsManager()
    monkeypatch.setenv("TASK_STALE_MINUTES", "10")

    await _run_offline_checker_one_cycle(monkeypatch, session, manager, now)

    assert stuck_task.retry_count == retry_count + 1
    assert stuck_task.status == expected_task_status
    assert stuck_task.completed_at == now
    assert session.channel_updates[-1]["status"] == expected_channel_status
    assert session.channel_updates[-1]["assigned_device_id"] is None
    assert session.channel_updates[-1]["assigned_at"] is None
    assert session.channel_updates[-1]["task_id"] is None
    assert session.closed is True


@pytest.mark.asyncio
async def test_lifespan_starts_and_cancels_offline_checker_task(monkeypatch):
    import app.main as main
    from app.services import pixelle_client

    created_task_names = []
    created_tasks = []

    class FakeTask:
        def __init__(self, name):
            self.name = name
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    async def fake_offline_checker():
        return None

    async def fake_style_lock_worker():
        return None

    async def fake_story_plan_worker():
        return None

    async def fake_one_sentence_reference_worker():
        return None

    def fake_create_task(coro):
        name = coro.cr_code.co_name
        created_task_names.append(name)
        coro.close()
        task = FakeTask(name)
        created_tasks.append(task)
        return task

    async def fake_gather(*tasks, return_exceptions=False):
        assert return_exceptions is True
        return list(tasks)

    monkeypatch.setattr(main, "_offline_checker", fake_offline_checker)
    monkeypatch.setattr(main, "_style_lock_worker", fake_style_lock_worker)
    monkeypatch.setattr(main, "_story_plan_worker", fake_story_plan_worker)
    monkeypatch.setattr(main, "_one_sentence_reference_worker", fake_one_sentence_reference_worker)
    monkeypatch.setattr(main.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(main.asyncio, "gather", fake_gather)
    monkeypatch.setattr(main.ai_generator, "aclose", AsyncMock())
    close_pixelle_client = AsyncMock()
    monkeypatch.setattr(pixelle_client, "close_client", close_pixelle_client)

    sentinel = object()
    previous_override = main.app.dependency_overrides.get(main.get_db, sentinel)
    main.app.dependency_overrides[main.get_db] = lambda: None
    try:
        async with main.lifespan(main.app):
            assert created_task_names == [
                "fake_offline_checker",
                "fake_style_lock_worker",
                "fake_story_plan_worker",
                "fake_one_sentence_reference_worker",
            ]
            assert len(created_tasks) == 4
    finally:
        if previous_override is sentinel:
            main.app.dependency_overrides.pop(main.get_db, None)
        else:
            main.app.dependency_overrides[main.get_db] = previous_override

    assert [task.cancelled for task in created_tasks] == [True, True, True, True]
    main.ai_generator.aclose.assert_awaited_once()
    close_pixelle_client.assert_awaited_once()


async def _run_offline_checker_one_cycle(monkeypatch, session, manager, now):
    import app.domains.device_operations.status_lifecycle as lifecycle
    import app.ws_manager as ws_manager_module

    sleep_calls = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 1:
            return None
        raise asyncio.CancelledError()

    monkeypatch.setattr(lifecycle.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(lifecycle, "SessionLocal", lambda: session)
    monkeypatch.setattr(lifecycle, "bj_now", lambda: now)
    monkeypatch.setattr(ws_manager_module, "pair_ws_manager", manager)

    with pytest.raises(asyncio.CancelledError):
        await lifecycle.offline_checker()
