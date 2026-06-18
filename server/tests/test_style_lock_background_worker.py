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
