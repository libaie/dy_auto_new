"""Real service regressions for crashed leases and concurrent image dispatch."""
import asyncio
from datetime import timedelta

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import bj_now
from app.db_models import Base, ImageCreationTask, ProductionJob
from app.services import image_creation_service as images
from app.services.production_queue_service import claim_next_job, fail_job, mark_job_completed, retry_job_without_attempt
from app.services.production_worker_service import run_real_worker_step
from tests.test_image_creation_strategy_snapshot import _seed_model
from tests.test_video_production_real_worker_step import _run_with_jobs


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


def _queued_image(db):
    model = _seed_model(db)
    task = ImageCreationTask(mode="text_to_image", capability_key="text_to_image", prompt="test",
        status="queued", model_id=model.id, pixelle_payload_json={"external_task_id": "stable-external", "prompt": "test"})
    db.add(task)
    db.commit()
    return task


def test_actual_real_worker_recovers_expired_lease(db):
    run = _run_with_jobs(db, job_count=1)
    job = claim_next_job(db, "crashed", plan_id=run.production_plan_id)
    job.leased_until = bj_now() - timedelta(seconds=1)
    db.commit()
    result = run_real_worker_step(db, run.id, lease_id="replacement")
    assert result["processed"] == 1
    assert result["items"][0]["error_code"] == "SEGMENT_PLAN_MISSING"
    db.refresh(job)
    assert job.status == "failed"


def test_actual_real_worker_does_not_steal_active_lease(db):
    run = _run_with_jobs(db, job_count=1)
    job = claim_next_job(db, "active", plan_id=run.production_plan_id)
    assert run_real_worker_step(db, run.id, lease_id="replacement")["processed"] == 0
    db.refresh(job)
    assert job.lease_id == "active"


@pytest.mark.parametrize("operation", ["fail", "retry", "complete"])
def test_stale_session_cannot_write_new_worker_lease(sessions, operation):
    with sessions() as old, sessions() as new:
        run = _run_with_jobs(old, job_count=1)
        job = claim_next_job(old, "old", plan_id=run.production_plan_id)
        job_id = job.id
        new.query(ProductionJob).filter_by(id=job_id).update({"lease_id": "new"})
        new.commit()
        with pytest.raises(ValueError):
            if operation == "fail":
                fail_job(old, job_id, "OLD", "late failure", False, expected_lease_id="old")
            elif operation == "retry":
                retry_job_without_attempt(old, job_id, "OLD", "late retry", expected_lease_id="old")
            else:
                mark_job_completed(old, job_id, expected_lease_id="old")
        new.expire_all()
        current = new.get(ProductionJob, job_id)
        assert current.status == "leased"
        assert current.lease_id == "new"
        assert current.attempt_count == 0


@pytest.mark.asyncio
async def test_image_dispatch_independent_sessions_only_submits_once(sessions, monkeypatch):
    with sessions() as seed:
        task_id = _queued_image(seed).id
    started, finish = asyncio.Event(), asyncio.Event()
    calls = []
    async def provider(**kwargs):
        calls.append(kwargs["external_task_id"])
        started.set()
        await finish.wait()
        return {"task_id": "provider-first"}
    monkeypatch.setattr(images, "submit_image_create", provider)
    with sessions() as first, sessions() as second:
        stale = second.get(ImageCreationTask, task_id)
        assert stale.capacity_lease_id is None
        pending = asyncio.create_task(images.dispatch_queued_image_task(first, task_id))
        await started.wait()
        with sessions() as observer:
            current = observer.get(ImageCreationTask, task_id)
            assert current.capacity_lease_id
            current.error_message = "independent write during submit"
            observer.commit()
        assert stale.capacity_lease_id is None
        try:
            with pytest.raises(HTTPException) as conflict:
                await asyncio.wait_for(images.dispatch_queued_image_task(second, task_id), timeout=.2)
            assert conflict.value.status_code == 409
        finally:
            finish.set()
            await pending
        second.expire_all()
        saved = second.get(ImageCreationTask, task_id)
        assert saved.pixelle_task_id == "provider-first"
        assert saved.external_task_id == "stable-external"
        assert calls == ["stable-external"]


@pytest.mark.asyncio
async def test_ambiguous_image_submit_preserves_identity_and_cannot_resubmit(sessions, monkeypatch):
    async def provider(**kwargs):
        raise httpx.ReadTimeout("response lost")
    monkeypatch.setattr(images, "submit_image_create", provider)
    with sessions() as db:
        task = _queued_image(db)
        with pytest.raises(HTTPException) as failure:
            await images.dispatch_queued_image_task(db, task.id)
        assert failure.value.status_code == 502
        db.refresh(task)
        assert task.external_task_id == "stable-external"
        with pytest.raises(HTTPException) as conflict:
            await images.dispatch_queued_image_task(db, task.id)
        assert conflict.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("late_failure", [False, True])
async def test_late_image_response_cannot_overwrite_reconciled_provider_id(sessions, monkeypatch, late_failure):
    with sessions() as db:
        task_id = _queued_image(db).id
    async def provider(**kwargs):
        with sessions() as other:
            other.query(ImageCreationTask).filter_by(id=task_id).update({
                "status": "running", "pixelle_task_id": "reconciled-id", "provider_task_id": "reconciled-id"})
            other.commit()
        if late_failure:
            raise httpx.ReadTimeout("late failure after reconciliation")
        return {"task_id": "late-id"}
    monkeypatch.setattr(images, "submit_image_create", provider)
    with sessions() as db:
        with pytest.raises(HTTPException) as conflict:
            await images.dispatch_queued_image_task(db, task_id)
        assert conflict.value.status_code == 409
        db.expire_all()
        assert db.get(ImageCreationTask, task_id).pixelle_task_id == "reconciled-id"


def _real_provider_run(db, monkeypatch):
    from tests.test_video_production_real_worker_step import _linked_run_with_image_job
    _seed_model(db, config_extra={
        "real_paid_allowed": True, "supports_external_task_id": True,
        "supports_task_query": True, "returns_asset_url": True, "returns_usage": True,
        "estimated_cost": .01, "max_concurrent_tasks": 1,
    })
    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    return _linked_run_with_image_job(db)


def test_recovered_worker_reuses_already_submitted_provider_id(sessions, monkeypatch):
    from app.services import video_production_service as video
    calls = {"submit": 0, "sync": []}
    async def submit(**kwargs):
        calls["submit"] += 1
        return {"stage_task_id": "existing-provider-id"}
    async def sync(db, task_id):
        calls["sync"].append(task_id)
        return {"status": "running"}
    monkeypatch.setattr(video, "submit_image_batch", submit)
    monkeypatch.setattr(video, "get_stage_task", sync)
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        first = run_real_worker_step(db, run.id, lease_id="old")
        assert first["items"][0]["error_code"] == "PROVIDER_STAGE_TASK_SYNC_REQUIRED"
        job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
        job.status = "leased"
        job.lease_id = "crashed"
        job.leased_until = bj_now() - timedelta(seconds=1)
        job.retry_after = None
        db.commit()
        second = run_real_worker_step(db, run.id, lease_id="new")
        assert second["processed"] == 1
        assert second["items"][0]["error_code"] == "PROVIDER_STAGE_TASK_SYNC_REQUIRED"
        assert calls == {"submit": 1, "sync": ["existing-provider-id", "existing-provider-id"]}
        assert job.attempt_count == 0


@pytest.mark.parametrize("outcome", ["running", "failed", "exception", "completed"])
def test_real_worker_late_provider_result_cannot_mutate_new_lease(sessions, monkeypatch, outcome):
    from app.db_models import ProductionSegment, VideoProductionAsset
    from app.services import video_production_service as video
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
        job_id, segment_id = job.id, segment.id
        async def submit(**kwargs):
            return {"stage_task_id": "old-provider-id"}
        async def sync(db_arg, task_id):
            # Simulate a lease reclaimed by the same caller identity: deadline is the fence.
            with sessions() as replacement:
                replacement.query(ProductionJob).filter_by(id=job_id).update({
                    "lease_id": "worker", "leased_until": bj_now() + timedelta(minutes=10)})
                replacement.query(ProductionSegment).filter_by(id=segment_id).update({"status": "video_running"})
                replacement.commit()
            if outcome == "exception":
                raise httpx.ReadTimeout("late error")
            if outcome == "completed":
                return {"status": "completed", "usage": {"cost": .01}, "assets": [{
                    "production_segment_id": segment_id, "url": "https://cdn.test/late.png",
                    "storage_path": "output/late.png", "checksum": "late", "copy_status": "persisted",
                }]}
            return {"status": outcome}
        monkeypatch.setattr(video, "submit_image_batch", submit)
        monkeypatch.setattr(video, "get_stage_task", sync)
        run_real_worker_step(db, run.id, lease_id="worker")
        db.expire_all()
        current = db.get(ProductionJob, job_id)
        assert current.status == "leased"
        assert current.lease_id == "worker"
        assert current.attempt_count == 0
        assert current.provider_task_id is None
        assert db.get(ProductionSegment, segment_id).status == "video_running"
        assert db.query(VideoProductionAsset).count() == 0


@pytest.mark.asyncio
async def test_immediate_creation_claim_blocks_concurrent_dispatch(sessions, monkeypatch):
    from app.db_models import ImageCreationTask
    seen = []
    async def provider(**kwargs):
        with sessions() as other:
            task = other.query(ImageCreationTask).one()
            assert task.capacity_lease_id
            with pytest.raises(HTTPException) as conflict:
                await images.dispatch_queued_image_task(other, task.id)
            assert conflict.value.status_code == 409
            seen.append(task.external_task_id)
        return {"task_id": "immediate-provider"}
    monkeypatch.setattr(images, "submit_image_create", provider)
    with sessions() as db:
        model = _seed_model(db)
        task = await images.create_image_task(db, {"mode": "text_to_image", "model_id": model.id, "prompt": "immediate", "count": 1})
        assert task.pixelle_task_id == "immediate-provider"
        assert seen == [task.id]


@pytest.mark.asyncio
async def test_image_submit_without_provider_id_requires_reconciliation(sessions, monkeypatch):
    async def provider(**kwargs):
        return {"ok": True}
    monkeypatch.setattr(images, "submit_image_create", provider)
    with sessions() as db:
        task = _queued_image(db)
        with pytest.raises(HTTPException) as failure:
            await images.dispatch_queued_image_task(db, task.id)
        assert failure.value.status_code == 502
        db.refresh(task)
        assert task.status == "failed"
        assert task.external_task_id == "stable-external"
        assert task.pixelle_task_id is None
        assert "Reconcile" in task.repair_action
