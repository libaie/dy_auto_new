import asyncio

import pytest


@pytest.mark.asyncio
async def test_style_lock_background_worker_calls_worker_step(monkeypatch):
    from app import main
    from app.domains.ai_video_series import style_lock

    calls = []

    class FakeSession:
        def close(self):
            calls.append(("closed", None))

    async def fake_worker_step(db, *, lease_id, batch_size):
        calls.append((lease_id, batch_size, db.__class__.__name__))
        raise asyncio.CancelledError()

    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(style_lock, "run_style_lock_worker_step", fake_worker_step)

    with pytest.raises(asyncio.CancelledError):
        await main._style_lock_worker(interval_seconds=0.01, batch_size=2)

    assert calls[0][1] == 2
    assert calls[0][2] == "FakeSession"
    assert calls[-1] == ("closed", None)


@pytest.mark.asyncio
async def test_story_plan_background_worker_calls_worker_step(monkeypatch):
    from app import main
    from app.domains.ai_video_series import story_planning

    calls = []

    class FakeSession:
        def close(self):
            calls.append(("closed", None))

    async def fake_worker_step(db, *, lease_id, batch_size):
        calls.append((lease_id, batch_size, db.__class__.__name__))
        raise asyncio.CancelledError()

    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(story_planning, "run_story_plan_worker_step", fake_worker_step)

    with pytest.raises(asyncio.CancelledError):
        await main._story_plan_worker(interval_seconds=0.01, batch_size=2)

    assert calls[0][0].startswith("story-plan-worker:")
    assert calls[0][1] == 2
    assert calls[0][2] == "FakeSession"
    assert calls[-1] == ("closed", None)


@pytest.mark.asyncio
async def test_real_video_background_worker_calls_threaded_cycle(monkeypatch):
    from app import main

    calls = []

    async def fake_to_thread(fn, lease_id, batch_size):
        calls.append((fn.__name__, lease_id, batch_size))
        raise asyncio.CancelledError()

    monkeypatch.setattr(main.asyncio, "to_thread", fake_to_thread)

    with pytest.raises(asyncio.CancelledError):
        await main._real_video_production_worker(interval_seconds=0.01, batch_size=3)

    assert calls[0][0] == "_run_real_video_production_worker_cycle"
    assert calls[0][1].startswith("real-video-worker:")
    assert calls[0][2] == 3


def test_real_video_background_worker_is_opt_in(monkeypatch):
    from app import main

    monkeypatch.delenv("REAL_VIDEO_WORKER_ENABLED", raising=False)
    assert main._real_video_worker_enabled() is False

    monkeypatch.setenv("REAL_VIDEO_WORKER_ENABLED", "0")
    assert main._real_video_worker_enabled() is False

    monkeypatch.setenv("REAL_VIDEO_WORKER_ENABLED", "true")
    assert main._real_video_worker_enabled() is True
