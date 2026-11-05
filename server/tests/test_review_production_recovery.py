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
    from app.db_models import ProductionSegment, VideoProductionAsset, ProviderStageTask, ProviderCostReservation, ProductionPlan
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
                replacement.query(ProviderStageTask).filter_by(job_id=job_id).update({
                    "status": "sync_required", "response_summary_json": {"message": "new worker state"}})
                replacement.query(ProviderCostReservation).update({"status": "submitted"})
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
        provider_task = db.query(ProviderStageTask).filter_by(job_id=job_id).one()
        assert provider_task.status == "sync_required"
        assert provider_task.response_summary_json == {"message": "new worker state"}
        reservation = db.query(ProviderCostReservation).one()
        assert reservation.status == "submitted"
        assert reservation.actual_cost is None
        assert db.get(ProductionPlan, run.production_plan_id).current_cost == 0


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


@pytest.mark.parametrize("outcome", ["accepted", "exception", "missing_id"])
@pytest.mark.parametrize("reconciled", [False, True])
def test_real_worker_stale_submit_preserves_shared_provider_state(sessions, monkeypatch, outcome, reconciled):
    from app.db_models import ProviderStageTask, ProviderCostReservation, ProductionPlan
    from app.services import video_production_service as video
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
        job_id = job.id
        async def submit(**kwargs):
            with sessions() as replacement:
                replacement.query(ProductionJob).filter_by(id=job_id).update({
                    "lease_id": "new", "leased_until": bj_now() + timedelta(minutes=10)})
                task = replacement.query(ProviderStageTask).filter_by(job_id=job_id).one()
                # The submission identity is durable even if the accepted response is lost.
                assert task.external_task_id == kwargs["template_config"]["external_task_id"]
                if reconciled:
                    task.status = "sync_required"
                    task.provider_task_id = "replacement-provider"
                    task.response_summary_json = {"message": "new worker state"}
                    replacement.query(ProviderCostReservation).update({"status": "submitted"})
                replacement.commit()
            if outcome == "exception":
                raise httpx.ReadTimeout("accepted request, response lost")
            if outcome == "missing_id":
                return {"ok": True}
            return {"stage_task_id": "late-provider"}
        async def unexpected_sync(*args, **kwargs):
            pytest.fail("A stale submit owner must not continue querying the provider")
        monkeypatch.setattr(video, "submit_image_batch", submit)
        monkeypatch.setattr(video, "get_stage_task", unexpected_sync)
        run_real_worker_step(db, run.id, lease_id="old")
        db.expire_all()
        current = db.get(ProductionJob, job_id)
        assert current.lease_id == "new"
        assert current.status == "leased"
        task = db.query(ProviderStageTask).filter_by(job_id=job_id).one()
        reservation = db.query(ProviderCostReservation).one()
        assert task.external_task_id == task.id
        assert task.status == ("sync_required" if reconciled else "submitted")
        assert task.provider_task_id == ("replacement-provider" if reconciled else None)
        assert task.response_summary_json == ({"message": "new worker state"} if reconciled else {})
        assert reservation.status == ("submitted" if reconciled else "active_unsubmitted")
        assert reservation.actual_cost is None
        assert db.get(ProductionPlan, run.production_plan_id).current_cost == 0


def test_worker_provider_result_and_cost_become_visible_atomically(sessions, monkeypatch):
    from sqlalchemy import event, select
    from app.db_models import ProviderStageTask, ProviderCostReservation, ProductionPlan
    from app.services.provider_stage_executor import ProviderStageExecutor
    from tests.test_provider_stage_executor import _capability, TransactionAssertingProviderClient
    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    with sessions() as db:
        run = _run_with_jobs(db, job_count=1)
        job = claim_next_job(db, "worker", plan_id=run.production_plan_id)
        run_id, plan_id, job_id = run.id, job.plan_id, job.id
        lease = (job.lease_id, job.leased_until)
        client = TransactionAssertingProviderClient(db)
        engine = db.get_bind()
        observed = []
        inspecting = False
        def observe_visibility(conn, cursor, statement, parameters, context, executemany):
            nonlocal inspecting
            if inspecting:
                return
            inspecting = True
            try:
                with engine.connect() as observer:
                    state = observer.execute(select(ProviderStageTask.status).where(ProviderStageTask.job_id == job_id)).scalar()
                    if state == "succeeded":
                        reservation = observer.execute(select(ProviderCostReservation.status)).scalar()
                        cost = observer.execute(select(ProductionPlan.current_cost).where(ProductionPlan.id == plan_id)).scalar()
                        observed.append((state, reservation, cost))
            finally:
                inspecting = False
        event.listen(engine, "after_cursor_execute", observe_visibility)
        try:
            result = asyncio.run(ProviderStageExecutor(client).execute(
                db, run_id=run_id, plan_id=plan_id, job_id=job_id,
                target_type=job.target_type, target_id=job.target_id, stage=job.stage,
                provider="test", model_name="test", estimated_cost=.5,
                payload={"prompt": "atomic"}, capability=_capability(), worker_lease=lease,
            ))
            assert result.status == "success"
            db.expire_all()
            assert db.query(ProviderStageTask).filter_by(job_id=job_id).one().status == "succeeded"
            assert observed
            assert all(state == ("succeeded", "settled", .37) for state in observed)
        finally:
            event.remove(engine, "after_cursor_execute", observe_visibility)


@pytest.mark.parametrize("boundary", ["download", "download_failure", "audit", "audit_second"])
def test_real_worker_late_asset_io_preserves_replacement_state(sessions, monkeypatch, tmp_path, boundary):
    from app.db_models import VideoProductionAsset, VideoReviewRecord, VideoProductionRun
    from app.services import video_production_service as video
    from app.services import asset_storage_guard as storage
    from app.routers import audit
    monkeypatch.chdir(tmp_path)
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        if boundary.startswith("audit"):
            _seed_model(db, name_prefix="audit", config_extra={"scene_key": "quality_audit", "scene_keys": ["quality_audit"]})
        job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
        job_id, run_id, segment_id = job.id, run.id, segment.id
        called = []
        audit_calls = []
        def replace_lease():
            with sessions() as replacement:
                replacement.query(ProductionJob).filter_by(id=job_id).update({
                    "lease_id": "replacement", "leased_until": bj_now() + timedelta(minutes=10)})
                replacement.query(VideoProductionAsset).filter_by(run_id=run_id).update({
                    "status": "approved", "copy_status": "persisted", "storage_path": "replacement.png",
                    "checksum": "replacement-checksum"})
                replacement.query(VideoProductionRun).filter_by(id=run_id).update({"status": "completed", "current_stage": "final_review"})
                replacement.commit()
            called.append(boundary)
        async def submit(**kwargs):
            return {"stage_task_id": "asset-provider"}
        async def sync(*args):
            item = {"frame_id": segment_id, "production_segment_id": segment_id, "url": "https://cdn.test/image.png"}
            if boundary.startswith("audit"):
                item.update(storage_path="existing.png", checksum="existing", copy_status="persisted")
            items = [item, dict(item)] if boundary == "audit_second" else [item]
            return {"status": "completed", "usage": {"cost": .01}, "assets": items}
        def download(asset, target):
            assert target.name != f"{asset.id}.tmp.png"
            replace_lease()
            if boundary == "download_failure":
                raise httpx.ReadTimeout("late download error")
            target.write_bytes(b"\x89PNGtest")
        def do_audit(*args, **kwargs):
            audit_calls.append(True)
            if boundary == "audit_second" and len(audit_calls) == 1:
                # A writer can proceed during every audit, including the first.
                with sessions() as observer:
                    observer.query(ProductionJob).filter_by(id=job_id).update({"error_message": "audit in flight"})
                    observer.commit()
            else:
                replace_lease()
            return {"score": .1, "pass_fail": False, "issues": ["late audit"]}
        monkeypatch.setattr(video, "submit_image_batch", submit)
        monkeypatch.setattr(video, "get_stage_task", sync)
        monkeypatch.setattr(storage, "_download_provider_url", download)
        monkeypatch.setattr(audit, "_do_audit", do_audit)
        run_real_worker_step(db, run_id, lease_id="old")
        assert called == [boundary]
        db.expire_all()
        assets = db.query(VideoProductionAsset).filter_by(run_id=run_id).all()
        assert len(assets) == (2 if boundary == "audit_second" else 1)
        assert all(asset.status == "approved" for asset in assets)
        assert all(asset.storage_path == "replacement.png" for asset in assets)
        assert all(asset.checksum == "replacement-checksum" for asset in assets)
        assert db.query(VideoReviewRecord).filter_by(run_id=run_id).count() == (1 if boundary == "audit_second" else 0)
        assert db.get(VideoProductionRun, run_id).status == "completed"
        assert db.get(ProductionJob, job_id).lease_id == "replacement"


@pytest.mark.parametrize("late_error", [False, True])
def test_stale_worker_cannot_recompute_run_after_replacement_completed(sessions, monkeypatch, late_error):
    from app.db_models import VideoProductionRun
    from app.services import video_production_service as video
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        run_id = run.id
        job_id = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one().id
        async def submit(**kwargs):
            return {"stage_task_id": "provider"}
        async def sync(*args):
            with sessions() as replacement:
                replacement.query(ProductionJob).filter_by(id=job_id).update({
                    "status": "completed", "lease_id": None, "leased_until": None,
                    "completed_at": bj_now(), "updated_at": bj_now()})
                replacement.query(VideoProductionRun).filter_by(id=run_id).update({
                    "status": "completed", "current_stage": "final_review"})
                replacement.commit()
            if late_error:
                raise httpx.ReadTimeout("old query failed")
            return {"status": "failed", "error": "old provider response"}
        monkeypatch.setattr(video, "submit_image_batch", submit)
        monkeypatch.setattr(video, "get_stage_task", sync)
        run_real_worker_step(db, run_id, lease_id="old")
        db.expire_all()
        assert db.get(VideoProductionRun, run_id).status == "completed"
        assert db.get(VideoProductionRun, run_id).current_stage == "final_review"


@pytest.mark.parametrize("review_outcome", ["blocked", "timeout"])
def test_late_deferred_review_cannot_overwrite_replacement_run(sessions, monkeypatch, review_outcome):
    from app.db_models import VideoProductionRun
    from app.services import video_production_service as video
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        model = _seed_model(db, name_prefix="agency", config_extra={
            "scene_key": "llm_agency_expert_review", "scene_keys": ["llm_agency_expert_review"]})
        model.model_type = "llm"
        db.commit()
        run_id = run.id
        job_id = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one().id
        called = []
        async def review(*args, **kwargs):
            with sessions() as replacement:
                replacement.query(ProductionJob).filter_by(id=job_id).update({
                    "lease_id": "replacement", "leased_until": bj_now() + timedelta(minutes=10)})
                replacement.query(VideoProductionRun).filter_by(id=run_id).update({
                    "status": "completed", "current_stage": "final_review", "model_trace_json": {"newer": "replacement"}})
                replacement.commit()
            called.append(review_outcome)
            if review_outcome == "timeout":
                raise asyncio.TimeoutError()
            return {"stage_status": "blocked", "error_code": "REVIEW_BLOCKED", "invocation_ids": []}
        async def unexpected_submit(**kwargs):
            pytest.fail("A stale review owner must not submit provider work")
        # Keep the real guard, trace storage, block, timeout, and worker code.
        monkeypatch.setattr(video, "_run_agency_stage_review", review)
        monkeypatch.setattr(video, "submit_image_batch", unexpected_submit)
        run_real_worker_step(db, run_id, lease_id="old")
        assert called == [review_outcome]
        db.expire_all()
        saved = db.get(VideoProductionRun, run_id)
        assert saved.status == "completed"
        assert saved.current_stage == "final_review"
        assert saved.model_trace_json == {"newer": "replacement"}
        assert db.get(ProductionJob, job_id).lease_id == "replacement"


@pytest.mark.parametrize("transition", ["retry_wait", "failed", "completed", "blocked"])
def test_transition_handoff_cannot_recompute_replacement_state(sessions, monkeypatch, transition):
    from app.db_models import VideoProductionRun
    from app.services import video_production_service as video
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        run_id, segment_id = run.id, segment.id
        job_id = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one().id
        if transition == "blocked":
            model = _seed_model(db, name_prefix="agency", config_extra={
                "scene_key": "llm_agency_expert_review", "scene_keys": ["llm_agency_expert_review"]})
            model.model_type = "llm"
            db.commit()
            async def review(*args, **kwargs):
                return {"stage_status": "blocked", "invocation_ids": []}
            monkeypatch.setattr(video, "_run_agency_stage_review", review)
        async def submit(**kwargs):
            return {"stage_task_id": "provider"}
        async def sync(*args):
            if transition == "completed":
                return {"status": "completed", "usage": {"cost": .01}, "assets": [{
                    "frame_id": segment_id, "production_segment_id": segment_id,
                    "url": "https://cdn.test/image.png", "storage_path": "image.png",
                    "checksum": "saved", "copy_status": "persisted"}]}
            return {"status": "running" if transition == "retry_wait" else "failed"}
        monkeypatch.setattr(video, "submit_image_batch", submit)
        monkeypatch.setattr(video, "get_stage_task", sync)
        original_refresh = db.refresh
        fired = []
        def refresh(instance, *args, **kwargs):
            # Observe durable DB state, not an expired or refreshed ORM snapshot.
            # Replacement may advance immediately after the transition is exposed.
            if isinstance(instance, ProductionJob) and not fired:
                with sessions() as replacement:
                    current = replacement.get(ProductionJob, job_id)
                    if current.status == transition:
                        current.status = "completed"
                        current.lease_id = None
                        current.leased_until = None
                        current.updated_at = bj_now()
                        replacement.query(VideoProductionRun).filter_by(id=run_id).update({
                            "status": "completed", "current_stage": "final_review"})
                        replacement.commit()
                        fired.append(True)
            return original_refresh(instance, *args, **kwargs)
        monkeypatch.setattr(db, "refresh", refresh)
        run_real_worker_step(db, run_id, lease_id="old")
        assert fired, "Transition handoff was not exercised"
        db.expire_all()
        assert db.get(VideoProductionRun, run_id).status == "completed"
        assert db.get(VideoProductionRun, run_id).current_stage == "final_review"


def test_execute_entry_does_not_adopt_replacement_lease(sessions, monkeypatch):
    from app.db_models import ProviderStageTask
    from app.services import video_production_service as video
    from app.services import production_worker_service as worker
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        job_id = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one().id
        calls = []
        original = worker.execute_real_job
        async def replace_at_entry(db_arg, run_arg, job_arg, **kwargs):
            with sessions() as replacement:
                replacement.query(ProductionJob).filter_by(id=job_id).update({
                    "lease_id": "replacement", "leased_until": bj_now() + timedelta(minutes=10)})
                replacement.commit()
            return await original(db_arg, run_arg, job_arg, **kwargs)
        async def submit(**kwargs):
            calls.append("old worker submitted")
            return {"stage_task_id": "old-provider"}
        async def sync(*args):
            return {"status": "running"}
        monkeypatch.setattr(worker, "execute_real_job", replace_at_entry)
        monkeypatch.setattr(video, "submit_image_batch", submit)
        monkeypatch.setattr(video, "get_stage_task", sync)
        worker.run_real_worker_step(db, run.id, lease_id="old")
        db.expire_all()
        assert calls == []
        assert db.query(ProviderStageTask).count() == 0
        assert db.get(ProductionJob, job_id).lease_id == "replacement"


@pytest.mark.parametrize("replacement_name", ["replacement", "worker"])
def test_claim_refresh_preserves_original_claim_authority(sessions, monkeypatch, replacement_name):
    from app.db_models import ProviderStageTask, ProductionSegment, VideoProductionRun
    from app.services import video_production_service as video
    with sessions() as db:
        run, segment = _real_provider_run(db, monkeypatch)
        run_id, segment_id = run.id, segment.id
        job_id = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one().id
        original_refresh = db.refresh
        fired, calls = [], []
        def refresh(instance, *args, **kwargs):
            if isinstance(instance, ProductionJob) and not fired:
                with sessions() as replacement:
                    current = replacement.get(ProductionJob, job_id)
                    if current.status == "leased":
                        current.lease_id = replacement_name
                        current.leased_until = bj_now() + timedelta(minutes=10)
                        replacement.query(ProductionSegment).filter_by(id=segment_id).update({"status": "video_running"})
                        replacement.query(VideoProductionRun).filter_by(id=run_id).update({"status": "completed"})
                        replacement.commit()
                        fired.append(True)
            return original_refresh(instance, *args, **kwargs)
        async def submit(**kwargs):
            calls.append("old worker submitted")
            return {"stage_task_id": "old-provider"}
        async def sync(*args):
            return {"status": "running"}
        monkeypatch.setattr(db, "refresh", refresh)
        monkeypatch.setattr(video, "submit_image_batch", submit)
        monkeypatch.setattr(video, "get_stage_task", sync)
        run_real_worker_step(db, run_id, lease_id="worker")
        assert fired
        db.expire_all()
        assert calls == []
        assert db.query(ProviderStageTask).count() == 0
        assert db.get(ProductionJob, job_id).lease_id == replacement_name
        assert db.get(ProductionSegment, segment_id).status == "video_running"
        assert db.get(VideoProductionRun, run_id).status == "completed"
