from datetime import timedelta

import pytest

from app.config import bj_now
from app.db_models import (
    Episode,
    ProductionJob,
    ProductionPlan,
    ProviderCostReservation,
    ProviderStageTask,
    Series,
    VideoProductionRun,
)
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.production_queue_service import enqueue_job
from app.services.production_state_contract import (
    PROVIDER_TASK_CANCELLED,
    PROVIDER_TASK_FAILED,
    PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
    PROVIDER_TASK_RUNNING,
    PROVIDER_TASK_SUBMITTED,
    PROVIDER_TASK_SUCCEEDED,
    PROVIDER_TASK_SYNC_REQUIRED,
)
from app.services.provider_stage_executor import (
    PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT,
    ProviderStageExecutor,
)
from app.services.provider_stage_task_service import request_hash


class FakeProviderClient:
    def __init__(self, *, sync_result=None):
        self.sync_result = sync_result or {
            "status": "succeeded",
            "asset_url": "https://cdn.example/asset.mp4",
            "usage": {"actual_cost": 0.2, "units": {"seconds": 4}},
        }
        self.submits = []
        self.syncs = []

    async def submit(self, payload):
        self.submits.append(payload)
        return {"provider_task_id": "provider-new"}

    async def sync(self, provider_task_id):
        self.syncs.append(provider_task_id)
        return self.sync_result


@pytest.fixture(autouse=True)
def _clean_provider_stage_tables(db, monkeypatch):
    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    db.query(ProviderCostReservation).delete()
    db.query(ProviderStageTask).delete()
    db.commit()
    yield
    db.query(ProviderCostReservation).delete()
    db.query(ProviderStageTask).delete()
    db.commit()


def _capability(max_concurrent_tasks):
    return {
        "real_paid_allowed": True,
        "supports_external_task_id": True,
        "supports_task_query": True,
        "returns_asset_url": True,
        "returns_usage": True,
        "max_concurrent_tasks": max_concurrent_tasks,
    }


def test_provider_throttle_deployment_contract_documents_single_process_scope():
    assert PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT["enforcement_scope"] == "single_process"
    assert PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT["uses_process_local_lock"] is True
    assert PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT["uses_db_submit_claim"] is True
    assert PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT["cross_process_hard_quota"] is False
    assert PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT["requires_runtime_worker_count"] is True


def _context(db):
    series = Series(title="Provider Throttle", logline="Boundary closure", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(
        series_id=series.id,
        status="ready",
        target_total_duration_seconds=60,
        budget_limit=10.0,
        current_cost=0.0,
    )
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_link_status="linked",
    )
    db.add(run)
    db.commit()
    job = enqueue_job(
        db,
        plan.id,
        "production_segment",
        "new-seg",
        "image_generation",
        "new-seg:image:v1",
    )
    return plan, run, job


def _stage_task(db, plan, run, *, status, suffix, provider="seedance", model_name="seedream", stage="image_generation"):
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        target_type="production_segment",
        target_id=f"seg-{suffix}",
        stage=stage,
        provider=provider,
        model_name=model_name,
        request_hash=f"hash-{suffix}",
        idempotency_key=f"{run.id}:{stage}:production_segment:seg-{suffix}:{provider}:{model_name}",
        status=status,
        provider_task_id=f"provider-{suffix}",
    )
    db.add(task)
    db.commit()
    return task


def _existing_reserved_task_for_job(db, run, job, payload):
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=job.plan_id,
        job_id=job.id,
        target_type=job.target_type,
        target_id=job.target_id,
        stage=job.stage,
        provider="seedance",
        model_name="seedream",
        request_hash=request_hash(payload),
        idempotency_key=f"{run.id}:{job.stage}:{job.target_type}:{job.target_id}:seedance:seedream",
        status="reserved",
        provider_task_id=None,
    )
    db.add(task)
    db.commit()
    return task


@pytest.mark.asyncio
async def test_provider_throttle_sets_job_retry_wait_before_creating_task_or_reservation(db):
    plan, run, job = _context(db)
    job.lease_id = "worker-a"
    job.leased_until = bj_now() + timedelta(minutes=5)
    db.commit()
    _stage_task(db, plan, run, status=PROVIDER_TASK_SUBMITTED, suffix="active-a")
    _stage_task(db, plan, run, status=PROVIDER_TASK_SYNC_REQUIRED, suffix="active-b")
    _stage_task(db, plan, run, status=PROVIDER_TASK_SUCCEEDED, suffix="terminal")
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="new-seg",
            stage="image_generation",
            provider="seedance",
            model_name="seedream",
            estimated_cost=0.5,
            payload={"prompt": "make an image"},
            capability=_capability(max_concurrent_tasks=2),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_THROTTLED
    assert client.submits == []
    assert client.syncs == []
    assert db.query(ProviderStageTask).count() == 3
    assert db.query(ProviderCostReservation).count() == 0

    db.refresh(job)
    assert job.status == "retry_wait"
    assert job.error_code == ProductionErrorCode.PROVIDER_THROTTLED.value
    assert job.retry_after is not None
    assert job.lease_id is None
    assert job.leased_until is None


@pytest.mark.asyncio
async def test_missing_runtime_worker_count_blocks_paid_submit_before_side_effects(db, monkeypatch):
    monkeypatch.delenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", raising=False)
    plan, run, job = _context(db)
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="new-seg",
            stage="image_generation",
            provider="seedance",
            model_name="seedream",
            estimated_cost=0.5,
            payload={"prompt": "make an image"},
            capability=_capability(max_concurrent_tasks=2),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert exc_info.value.cause == "provider_submit_worker_count_required"
    assert client.submits == []
    assert client.syncs == []
    assert db.query(ProviderStageTask).count() == 0
    assert db.query(ProviderCostReservation).count() == 0


@pytest.mark.asyncio
async def test_multi_worker_runtime_blocks_paid_submit_before_side_effects(db, monkeypatch):
    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "2")
    plan, run, job = _context(db)
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="new-seg",
            stage="image_generation",
            provider="seedance",
            model_name="seedream",
            estimated_cost=0.5,
            payload={"prompt": "make an image"},
            capability=_capability(max_concurrent_tasks=2),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert exc_info.value.cause == "provider_cross_process_quota_required"
    assert client.submits == []
    assert client.syncs == []
    assert db.query(ProviderStageTask).count() == 0
    assert db.query(ProviderCostReservation).count() == 0


@pytest.mark.asyncio
async def test_existing_task_without_provider_task_id_is_still_throttled_before_submit(db):
    plan, run, job = _context(db)
    payload = {"prompt": "make an image"}
    _existing_reserved_task_for_job(db, run, job, payload)
    _stage_task(db, plan, run, status=PROVIDER_TASK_SUBMITTED, suffix="active-a")
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="new-seg",
            stage="image_generation",
            provider="seedance",
            model_name="seedream",
            estimated_cost=0.5,
            payload=payload,
            capability=_capability(max_concurrent_tasks=1),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_THROTTLED
    assert client.submits == []
    assert client.syncs == []
    assert db.query(ProviderStageTask).count() == 2
    assert db.query(ProviderCostReservation).count() == 0


@pytest.mark.asyncio
async def test_active_task_count_includes_all_repairable_nonterminal_statuses(db):
    plan, run, job = _context(db)
    for status in (
        PROVIDER_TASK_SUBMITTED,
        PROVIDER_TASK_RUNNING,
        PROVIDER_TASK_SYNC_REQUIRED,
        PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
    ):
        _stage_task(db, plan, run, status=status, suffix=status)
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="new-seg",
            stage="image_generation",
            provider="seedance",
            model_name="seedream",
            estimated_cost=0.5,
            payload={"prompt": "make an image"},
            capability=_capability(max_concurrent_tasks=4),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_THROTTLED
    assert client.submits == []


@pytest.mark.asyncio
async def test_terminal_provider_tasks_do_not_count_against_throttle(db):
    plan, run, job = _context(db)
    for status in (PROVIDER_TASK_SUCCEEDED, PROVIDER_TASK_FAILED, PROVIDER_TASK_CANCELLED):
        _stage_task(db, plan, run, status=status, suffix=status)
    client = FakeProviderClient()

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="new-seg",
        stage="image_generation",
        provider="seedance",
        model_name="seedream",
        estimated_cost=0.5,
        payload={"prompt": "make an image"},
        capability=_capability(max_concurrent_tasks=1),
    )

    assert result.status == "success"
    task = db.query(ProviderStageTask).filter_by(target_id="new-seg").one()
    assert client.submits == [{
        "prompt": "make an image",
        "external_task_id": task.id,
        "provider_stage_task_id": task.id,
        "provider_idempotency_key": task.id,
    }]
    assert db.query(ProviderStageTask).count() == 4


@pytest.mark.asyncio
async def test_pending_claimed_task_blocks_second_target_at_provider_capacity(db):
    plan, run, job = _context(db)
    first_client = FakeProviderClient(sync_result={"status": "running"})
    first = await ProviderStageExecutor(first_client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="new-seg",
        stage="image_generation",
        provider="seedance",
        model_name="seedream",
        estimated_cost=0.5,
        payload={"prompt": "make an image"},
        capability=_capability(max_concurrent_tasks=1),
    )
    second_job = enqueue_job(
        db,
        plan.id,
        "production_segment",
        "next-seg",
        "image_generation",
        "next-seg:image:v1",
    )
    second_client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(second_client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=second_job.id,
            target_type="production_segment",
            target_id="next-seg",
            stage="image_generation",
            provider="seedance",
            model_name="seedream",
            estimated_cost=0.5,
            payload={"prompt": "make another image"},
            capability=_capability(max_concurrent_tasks=1),
        )

    assert first.status == "blocked"
    assert exc_info.value.code == ProductionErrorCode.PROVIDER_THROTTLED
    task = db.query(ProviderStageTask).filter_by(target_id="new-seg").one()
    assert first_client.submits == [{
        "prompt": "make an image",
        "external_task_id": task.id,
        "provider_stage_task_id": task.id,
        "provider_idempotency_key": task.id,
    }]
    assert second_client.submits == []
