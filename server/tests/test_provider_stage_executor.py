import hashlib
import json

import pytest

from app.domains.video_production import provider_stage_executor as executor_module
from app.db.models import (
    Episode,
    ProductionAuditEvent,
    ProductionJob,
    ProductionPlan,
    ProviderCostReservation,
    ProviderStageTask,
    Series,
    VideoProductionRun,
)
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.video_production.production_queue_service import enqueue_job
from app.domains.video_production.production_state_contract import (
    COST_ACTIVE_UNSUBMITTED,
    COST_STALE_NEEDS_REPAIR,
    COST_SETTLED,
    COST_SUBMITTED,
    PROVIDER_TASK_CANCELLED,
    PROVIDER_TASK_FAILED,
    PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
    PROVIDER_TASK_RUNNING,
    PROVIDER_TASK_SYNC_REQUIRED,
    PROVIDER_TASK_SUCCEEDED,
)
from app.domains.video_production.provider_capability_service import (
    assert_real_paid_allowed,
    capability_from_model_config,
)
from app.domains.video_production.provider_stage_executor import ProviderStageExecutor
from app.domains.video_production.provider_stage_task_service import (
    get_or_create_stage_task,
    request_hash,
    set_task_status,
)


class FakeProviderClient:
    def __init__(self, *, submit_result=None, sync_result=None):
        self.submit_result = submit_result or {"provider_task_id": "provider-task-1"}
        self.sync_result = sync_result or {
            "status": "succeeded",
            "asset_url": "https://cdn.example/asset.mp4",
            "usage": {"cost": 0.37, "units": {"seconds": 4}},
        }
        self.submits = []
        self.syncs = []

    async def submit(self, payload):
        self.submits.append(payload)
        return self.submit_result

    async def sync(self, provider_task_id):
        self.syncs.append(provider_task_id)
        return self.sync_result


class TransactionAssertingProviderClient(FakeProviderClient):
    def __init__(self, db, **kwargs):
        super().__init__(**kwargs)
        self.db = db

    async def submit(self, payload):
        assert self.db.in_transaction() is False
        return await super().submit(payload)

    async def sync(self, provider_task_id):
        assert self.db.in_transaction() is False
        return await super().sync(provider_task_id)


class FailingSubmitProviderClient(FakeProviderClient):
    async def submit(self, payload):
        self.submits.append(payload)
        raise RuntimeError("provider unavailable")


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


def _capability(**overrides):
    capability = {
        "real_paid_allowed": True,
        "supports_external_task_id": True,
        "supports_task_query": True,
        "returns_asset_url": True,
        "returns_usage": True,
        "max_concurrent_tasks": 3,
    }
    capability.update(overrides)
    return capability


def _request_hash(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _existing_reserved_task(db, run, job, *, payload, provider="seedance", model_name="seedance-v1", status="reserved"):
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=job.plan_id,
        job_id=job.id,
        target_type=job.target_type,
        target_id=job.target_id,
        stage=job.stage,
        provider=provider,
        model_name=model_name,
        request_hash=_request_hash(payload),
        idempotency_key=f"{run.id}:{job.stage}:{job.target_type}:{job.target_id}:{provider}:{model_name}",
        status=status,
        provider_task_id=None,
    )
    db.add(task)
    db.commit()
    return task


def _reservation(db, plan, task, *, status=COST_ACTIVE_UNSUBMITTED):
    reservation = ProviderCostReservation(
        plan_id=plan.id,
        provider_stage_task_id=task.id,
        status=status,
        estimated_cost=0.5,
        reserved_cost=0.5,
        currency="CNY",
    )
    db.add(reservation)
    db.commit()
    return reservation


def _context(db, *, key_suffix="seg-1"):
    series = Series(title=f"Provider Executor {key_suffix}", logline="Boundary closure", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(
        series_id=series.id,
        status="ready",
        target_total_duration_seconds=60,
        budget_limit=5.0,
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
        key_suffix,
        "video_generation",
        f"{key_suffix}:video:v1",
    )
    return plan, run, job


@pytest.mark.asyncio
async def test_executor_submits_syncs_settles_and_audits_provider_stage(db):
    plan, run, job = _context(db)
    client = FakeProviderClient()

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-1",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert result.status == "success"
    assert client.syncs == ["provider-task-1"]

    task = db.query(ProviderStageTask).one()
    assert client.submits == [{
        "prompt": "make a clip",
        "duration": 4,
        "external_task_id": task.id,
        "provider_stage_task_id": task.id,
        "provider_idempotency_key": task.id,
    }]
    assert task.provider_task_id == "provider-task-1"
    assert task.external_task_id == task.id
    assert task.status == PROVIDER_TASK_SUCCEEDED
    assert task.response_summary_json["asset_url"] == "https://cdn.example/asset.mp4"
    assert result.data["provider_stage_task_id"] == task.id
    assert result.data["provider_result"]["status"] == "succeeded"

    reservation = db.query(ProviderCostReservation).one()
    assert reservation.provider_stage_task_id == task.id
    assert reservation.status == COST_SETTLED
    assert reservation.actual_cost == pytest.approx(0.37)
    assert reservation.units_json == {"seconds": 4}

    db.refresh(plan)
    assert plan.current_cost == pytest.approx(0.37)

    event = db.query(ProductionAuditEvent).filter_by(event_type="provider_stage.succeeded").one()
    assert event.run_id == run.id
    assert event.production_plan_id == plan.id
    assert event.provider_task_id == "provider-task-1"
    assert event.payload_json["provider_stage_task_id"] == task.id


@pytest.mark.asyncio
async def test_executor_rejects_completed_provider_result_with_failed_assets(db):
    plan, run, job = _context(db, key_suffix="seg-failed-asset")
    client = FakeProviderClient(sync_result={
        "status": "completed",
        "assets": [{
            "frame_id": "seg-failed-asset",
            "asset_type": "video_segment",
            "status": "failed",
            "error_code": "VIDEO_RENDER_FAILED",
            "message": "provider rejected payload",
        }],
        "usage": {"cost": 0.37},
    })

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-failed-asset",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert result.status == "blocked"
    assert result.code == ProductionErrorCode.PROVIDER_TASK_FAILED
    task = db.query(ProviderStageTask).one()
    assert task.status == PROVIDER_TASK_FAILED
    assert task.response_summary_json["failed_assets"][0]["error_code"] == "VIDEO_RENDER_FAILED"
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.status == COST_STALE_NEEDS_REPAIR


@pytest.mark.parametrize(
    "message",
    [
        "Seedance video submit failed: HTTP 429: The request has exceeded the quota.",
        "DashScope video submit failed: HTTP 400: Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment",
    ],
)
@pytest.mark.asyncio
async def test_retryable_quota_failed_asset_archives_stage_task_key_for_new_submit(db, message):
    plan, run, job = _context(db, key_suffix="seg-quota-asset")
    client = FakeProviderClient(sync_result={
        "status": "completed",
        "assets": [{
            "frame_id": "seg-quota-asset",
            "asset_type": "video_segment",
            "status": "failed",
            "error_code": "VIDEO_RENDER_FAILED",
            "message": message,
            "retryable": True,
        }],
        "usage": {"cost": 0.37},
    })

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-quota-asset",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert result.status == "blocked"
    assert result.code == ProductionErrorCode.PROVIDER_THROTTLED
    assert result.retryable is True
    old_task = db.query(ProviderStageTask).one()
    assert old_task.status == PROVIDER_TASK_FAILED
    assert old_task.error_code == ProductionErrorCode.PROVIDER_THROTTLED.value
    assert old_task.idempotency_key.endswith(f":archived:{old_task.id}")
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.status == COST_STALE_NEEDS_REPAIR

    recovery_client = FakeProviderClient()
    recovered = await ProviderStageExecutor(recovery_client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-quota-asset",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert recovered.status == "success"
    assert db.query(ProviderStageTask).count() == 2
    new_task = (
        db.query(ProviderStageTask)
        .filter(ProviderStageTask.id != old_task.id)
        .one()
    )
    assert recovery_client.submits == [{
        "prompt": "make a clip",
        "duration": 4,
        "external_task_id": new_task.id,
        "provider_stage_task_id": new_task.id,
        "provider_idempotency_key": new_task.id,
    }]


@pytest.mark.asyncio
async def test_retryable_quota_existing_failed_task_archives_key_for_new_submit(db):
    plan, run, job = _context(db, key_suffix="seg-existing-failed-quota")
    payload = {"prompt": "make a clip", "duration": 4}
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-existing-failed-quota",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        request_hash=_request_hash(payload),
        idempotency_key=f"{run.id}:video_generation:production_segment:seg-existing-failed-quota:seedance:seedance-v1",
        status=PROVIDER_TASK_FAILED,
        provider_task_id="provider-failed-quota",
        error_code=ProductionErrorCode.PROVIDER_TASK_FAILED.value,
    )
    db.add(task)
    db.flush()
    _reservation(db, plan, task, status=COST_SUBMITTED)
    db.commit()
    client = FakeProviderClient(sync_result={
        "status": "completed",
        "assets": [{
            "frame_id": "seg-existing-failed-quota",
            "asset_type": "video_segment",
            "status": "failed",
            "message": "DashScope video submit failed: HTTP 400: Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment",
            "retryable": True,
        }],
        "usage": {"cost": 0.37},
    })

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-existing-failed-quota",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload=payload,
        capability=_capability(),
    )

    assert result.code == ProductionErrorCode.PROVIDER_THROTTLED
    db.refresh(task)
    assert task.status == PROVIDER_TASK_FAILED
    assert task.error_code == ProductionErrorCode.PROVIDER_THROTTLED.value
    assert task.idempotency_key.endswith(f":archived:{task.id}")
    assert client.submits == []


@pytest.mark.asyncio
async def test_retryable_access_denied_without_billing_is_not_quota_failure(db):
    plan, run, job = _context(db, key_suffix="seg-access-denied")
    client = FakeProviderClient(sync_result={
        "status": "completed",
        "assets": [{
            "frame_id": "seg-access-denied",
            "asset_type": "video_segment",
            "status": "failed",
            "message": "Provider submit failed: HTTP 403: Access denied for this API key.",
            "retryable": True,
        }],
        "usage": {"cost": 0.37},
    })

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-access-denied",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert result.code == ProductionErrorCode.PROVIDER_TASK_FAILED
    task = db.query(ProviderStageTask).one()
    assert task.status == PROVIDER_TASK_FAILED
    assert ":archived:" not in task.idempotency_key


@pytest.mark.asyncio
async def test_existing_provider_task_syncs_without_resubmitting(db):
    plan, run, job = _context(db, key_suffix="seg-2")
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-2",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        request_hash=_request_hash({"prompt": "make a clip", "duration": 4}),
        idempotency_key=f"{run.id}:video_generation:production_segment:seg-2:seedance:seedance-v1",
        status=PROVIDER_TASK_SYNC_REQUIRED,
        provider_task_id="provider-existing",
    )
    db.add(task)
    db.commit()
    reservation = _reservation(db, plan, task, status=COST_SUBMITTED)
    client = FakeProviderClient()

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-2",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert result.status == "success"
    assert client.submits == []
    assert client.syncs == ["provider-existing"]
    assert db.query(ProviderStageTask).count() == 1
    db.refresh(task)
    db.refresh(reservation)
    assert task.status == PROVIDER_TASK_SUCCEEDED
    assert reservation.status == COST_SETTLED


@pytest.mark.asyncio
async def test_existing_provider_task_without_reservation_blocks_before_sync(db):
    plan, run, job = _context(db, key_suffix="seg-existing-no-reservation")
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-existing-no-reservation",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        request_hash=_request_hash({"prompt": "make a clip", "duration": 4}),
        idempotency_key=f"{run.id}:video_generation:production_segment:seg-existing-no-reservation:seedance:seedance-v1",
        status=PROVIDER_TASK_SYNC_REQUIRED,
        provider_task_id="provider-existing",
    )
    db.add(task)
    db.commit()
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-existing-no-reservation",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload={"prompt": "make a clip", "duration": 4},
            capability=_capability(),
        )

    assert exc_info.value.code == ProductionErrorCode.BUDGET_BLOCKED
    assert exc_info.value.cause == "provider_cost_reservation_missing"
    assert client.submits == []
    assert client.syncs == []


@pytest.mark.asyncio
async def test_existing_reserved_task_without_reservation_creates_reservation_before_submit(db):
    plan, run, job = _context(db, key_suffix="seg-missing-reservation")
    payload = {"prompt": "make a clip", "duration": 4}
    task = _existing_reserved_task(db, run, job, payload=payload)
    client = FakeProviderClient()

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-missing-reservation",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload=payload,
        capability=_capability(),
    )

    assert result.status == "success"
    db.refresh(task)
    assert client.submits == [{
        **payload,
        "external_task_id": task.id,
        "provider_stage_task_id": task.id,
        "provider_idempotency_key": task.id,
    }]
    assert task.status == PROVIDER_TASK_SUCCEEDED
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.provider_stage_task_id == task.id
    assert reservation.status == COST_SETTLED


@pytest.mark.asyncio
async def test_completed_provider_task_without_usage_cost_marks_reservation_stale(db):
    plan, run, job = _context(db, key_suffix="seg-missing-usage")
    client = FakeProviderClient(sync_result={"status": "succeeded", "asset_url": "https://cdn.example/asset.mp4"})

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-missing-usage",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload={"prompt": "make a clip", "duration": 4},
            capability=_capability(),
        )

    assert exc_info.value.code == ProductionErrorCode.BUDGET_BLOCKED
    assert exc_info.value.cause == "provider_usage_cost_missing"
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.status == COST_STALE_NEEDS_REPAIR
    assert reservation.actual_cost is None


@pytest.mark.asyncio
async def test_existing_reserved_task_without_reservation_does_not_submit_when_budget_blocks(db):
    plan, run, job = _context(db, key_suffix="seg-budget-block")
    plan.budget_limit = 0.1
    db.commit()
    payload = {"prompt": "make a clip", "duration": 4}
    task = _existing_reserved_task(db, run, job, payload=payload)
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-budget-block",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload=payload,
            capability=_capability(),
        )

    assert exc_info.value.code == ProductionErrorCode.BUDGET_BLOCKED
    assert client.submits == []
    assert client.syncs == []
    db.refresh(task)
    assert task.status == "reserved"
    assert task.provider_task_id is None
    assert db.query(ProviderCostReservation).count() == 0


@pytest.mark.asyncio
async def test_existing_submitted_without_provider_task_id_enters_repair_before_throttle_or_submit(db):
    plan, run, job = _context(db, key_suffix="seg-crash-submitted")
    payload = {"prompt": "make a clip", "duration": 4}
    task = _existing_reserved_task(db, run, job, payload=payload, status="submitted")
    reservation = _reservation(db, plan, task)
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-crash-submitted",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload=payload,
            capability=_capability(max_concurrent_tasks=1),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert client.submits == []
    assert client.syncs == []
    db.refresh(task)
    db.refresh(reservation)
    assert task.status == PROVIDER_TASK_MANUAL_REPAIR_REQUIRED
    assert task.provider_task_id is None
    assert task.error_code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED.value
    assert task.response_summary_json["cause"] == "provider_task_id_missing_after_submit_claim"
    assert reservation.status == COST_STALE_NEEDS_REPAIR


@pytest.mark.asyncio
async def test_existing_sync_required_without_provider_task_id_enters_repair_not_sync_required(db):
    plan, run, job = _context(db, key_suffix="seg-crash-sync")
    payload = {"prompt": "make a clip", "duration": 4}
    task = _existing_reserved_task(db, run, job, payload=payload, status=PROVIDER_TASK_SYNC_REQUIRED)
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-crash-sync",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload=payload,
            capability=_capability(max_concurrent_tasks=1),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert exc_info.value.code != ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED
    assert client.submits == []
    assert client.syncs == []
    db.refresh(task)
    assert task.status == PROVIDER_TASK_MANUAL_REPAIR_REQUIRED
    assert task.provider_task_id is None
    assert task.response_summary_json["cause"] == "provider_task_id_missing_after_submit_claim"


@pytest.mark.asyncio
async def test_capability_gate_blocks_before_task_or_reservation(db):
    plan, run, job = _context(db, key_suffix="seg-3")
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-3",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload={"prompt": "make a clip", "duration": 4},
            capability=_capability(real_paid_allowed=False),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert client.submits == []
    assert client.syncs == []
    assert db.query(ProviderStageTask).count() == 0
    assert db.query(ProviderCostReservation).count() == 0


@pytest.mark.asyncio
async def test_lost_submit_claim_without_provider_task_id_enters_repair_not_sync_required(db, monkeypatch):
    plan, run, job = _context(db, key_suffix="seg-claim")
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-claim",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        request_hash=_request_hash({"prompt": "make a clip", "duration": 4}),
        idempotency_key=f"{run.id}:video_generation:production_segment:seg-claim:seedance:seedance-v1",
        status="reserved",
        provider_task_id=None,
    )
    db.add(task)
    db.commit()
    monkeypatch.setattr(executor_module, "claim_stage_task_for_submit", lambda inner_db, task_id: False, raising=False)
    client = FakeProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-claim",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload={"prompt": "make a clip", "duration": 4},
            capability=_capability(),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert client.submits == []
    assert client.syncs == []
    db.refresh(task)
    assert task.status == PROVIDER_TASK_MANUAL_REPAIR_REQUIRED
    assert task.provider_task_id is None
    assert task.response_summary_json["cause"] == "provider_task_id_missing_after_submit_claim"
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.status == COST_STALE_NEEDS_REPAIR
    assert (
        db.query(ProviderStageTask)
        .filter(
            ProviderStageTask.status == PROVIDER_TASK_SYNC_REQUIRED,
            ProviderStageTask.provider_task_id.is_(None),
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_provider_io_is_not_awaited_inside_sqlalchemy_transaction(db):
    plan, run, job = _context(db, key_suffix="seg-tx")
    client = TransactionAssertingProviderClient(db)

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-tx",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert result.status == "success"


@pytest.mark.asyncio
async def test_submit_exception_marks_task_repairable_and_reservation_stale(db):
    plan, run, job = _context(db, key_suffix="seg-submit-fail")
    client = FailingSubmitProviderClient()

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-submit-fail",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload={"prompt": "make a clip", "duration": 4},
            capability=_capability(),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert client.syncs == []
    task = db.query(ProviderStageTask).one()
    assert client.submits == [{
        "prompt": "make a clip",
        "duration": 4,
        "external_task_id": task.id,
        "provider_stage_task_id": task.id,
        "provider_idempotency_key": task.id,
    }]
    assert task.status == PROVIDER_TASK_MANUAL_REPAIR_REQUIRED
    assert task.provider_task_id is None
    assert task.error_code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED.value
    assert "provider unavailable" in task.error_message
    assert task.response_summary_json["cause"] == "provider_submit_failed"
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.status == COST_STALE_NEEDS_REPAIR


@pytest.mark.asyncio
async def test_missing_provider_task_id_marks_task_repairable_and_reservation_stale(db):
    plan, run, job = _context(db, key_suffix="seg-missing-id")
    client = FakeProviderClient(submit_result={"status": "accepted"})

    with pytest.raises(ProductionRepairableError) as exc_info:
        await ProviderStageExecutor(client).execute(
            db,
            run_id=run.id,
            plan_id=plan.id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-missing-id",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            estimated_cost=0.5,
            payload={"prompt": "make a clip", "duration": 4},
            capability=_capability(),
        )

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED
    assert client.syncs == []
    task = db.query(ProviderStageTask).one()
    assert client.submits == [{
        "prompt": "make a clip",
        "duration": 4,
        "external_task_id": task.id,
        "provider_stage_task_id": task.id,
        "provider_idempotency_key": task.id,
    }]
    assert task.status == PROVIDER_TASK_MANUAL_REPAIR_REQUIRED
    assert task.provider_task_id is None
    assert task.response_summary_json["cause"] == "provider_task_id_missing"
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.status == COST_STALE_NEEDS_REPAIR


@pytest.mark.asyncio
async def test_pending_sync_returns_blocked_result_without_settling_success(db):
    plan, run, job = _context(db, key_suffix="seg-4")
    client = FakeProviderClient(sync_result={"status": "running", "progress": 0.4})

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-4",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert result.to_http_detail()["ok"] is False
    assert result.code == ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED
    assert client.syncs == ["provider-task-1"]

    task = db.query(ProviderStageTask).one()
    assert client.submits == [{
        "prompt": "make a clip",
        "duration": 4,
        "external_task_id": task.id,
        "provider_stage_task_id": task.id,
        "provider_idempotency_key": task.id,
    }]
    assert task.status == PROVIDER_TASK_SYNC_REQUIRED
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.status == COST_SUBMITTED
    assert reservation.actual_cost is None
    assert db.query(ProductionAuditEvent).filter_by(event_type="provider_stage.succeeded").count() == 0


@pytest.mark.parametrize(
    ("provider_status", "expected_status"),
    [
        ("failed", PROVIDER_TASK_FAILED),
        ("error", PROVIDER_TASK_FAILED),
        ("cancelled", PROVIDER_TASK_CANCELLED),
        ("canceled", PROVIDER_TASK_CANCELLED),
    ],
)
async def test_terminal_provider_sync_failure_marks_task_terminal_and_reservation_stale(
    db,
    provider_status,
    expected_status,
):
    plan, run, job = _context(db, key_suffix=f"seg-terminal-{provider_status}")
    client = FakeProviderClient(sync_result={"status": provider_status, "error": "provider stopped"})

    result = await ProviderStageExecutor(client).execute(
        db,
        run_id=run.id,
        plan_id=plan.id,
        job_id=job.id,
        target_type="production_segment",
        target_id=f"seg-terminal-{provider_status}",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        estimated_cost=0.5,
        payload={"prompt": "make a clip", "duration": 4},
        capability=_capability(),
    )

    assert result.status == "blocked"
    assert result.code == ProductionErrorCode.PROVIDER_TASK_FAILED
    assert result.retryable is False
    assert "explicit stage retry" in result.repair_action
    assert result.to_http_detail()["data"]["provider_result"]["status"] == provider_status
    task = db.query(ProviderStageTask).one()
    assert task.status == expected_status
    assert task.error_code == ProductionErrorCode.PROVIDER_TASK_FAILED.value
    reservation = db.query(ProviderCostReservation).one()
    assert reservation.status == COST_STALE_NEEDS_REPAIR
    assert db.query(ProductionAuditEvent).filter_by(event_type="provider_stage.succeeded").count() == 0


def test_capability_from_model_config_merges_config_provider_options_and_capability():
    capability = capability_from_model_config(
        {
            "config_json": {
                "max_concurrent_tasks": 2,
                "supports_external_task_id": True,
                "supports_task_query": True,
            },
            "provider_options": {
                "max_concurrent_tasks": 4,
                "returns_asset_url": True,
                "returns_usage": True,
            },
            "capability": {
                "max_concurrent_tasks": 6,
                "real_paid_allowed": True,
            },
        }
    )

    assert capability["supports_external_task_id"] is True
    assert capability["supports_task_query"] is True
    assert capability["returns_asset_url"] is True
    assert capability["returns_usage"] is True
    assert capability["real_paid_allowed"] is True
    assert capability["max_concurrent_tasks"] == 6


@pytest.mark.parametrize(
    "missing_key",
    ["supports_external_task_id", "supports_task_query", "returns_asset_url", "returns_usage"],
)
def test_assert_real_paid_allowed_requires_paid_execution_safety_capabilities(missing_key):
    capability = _capability()
    capability.pop(missing_key)

    with pytest.raises(ValueError) as exc_info:
        assert_real_paid_allowed(capability)

    assert exc_info.value.code == ProductionErrorCode.PROVIDER_SUBMIT_FAILED


def test_request_hash_is_stable_independent_of_key_order():
    assert request_hash({"prompt": "clip", "options": {"duration": 4, "seed": 7}}) == request_hash(
        {"options": {"seed": 7, "duration": 4}, "prompt": "clip"}
    )


def test_get_or_create_stage_task_is_idempotent_and_rejects_payload_drift(db):
    _plan, run, job = _context(db, key_suffix="seg-5")

    first, created = get_or_create_stage_task(
        db,
        run_id=run.id,
        plan_id=job.plan_id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-5",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        payload={"prompt": "same", "duration": 4},
    )
    second, second_created = get_or_create_stage_task(
        db,
        run_id=run.id,
        plan_id=job.plan_id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-5",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        payload={"duration": 4, "prompt": "same"},
    )

    assert created is True
    assert second_created is False
    assert second.id == first.id

    with pytest.raises(ValueError):
        get_or_create_stage_task(
            db,
            run_id=run.id,
            plan_id=job.plan_id,
            job_id=job.id,
            target_type="production_segment",
            target_id="seg-5",
            stage="video_generation",
            provider="seedance",
            model_name="seedance-v1",
            payload={"prompt": "changed", "duration": 4},
        )


def test_set_task_status_rejects_invalid_transition(db):
    _plan, run, job = _context(db, key_suffix="seg-6")
    task, _created = get_or_create_stage_task(
        db,
        run_id=run.id,
        plan_id=job.plan_id,
        job_id=job.id,
        target_type="production_segment",
        target_id="seg-6",
        stage="video_generation",
        provider="seedance",
        model_name="seedance-v1",
        payload={"prompt": "same", "duration": 4},
    )
    set_task_status(db, task, "submitted")
    set_task_status(db, task, PROVIDER_TASK_SUCCEEDED)

    with pytest.raises(ValueError):
        set_task_status(db, task, PROVIDER_TASK_RUNNING)
