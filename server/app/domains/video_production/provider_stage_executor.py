import os
import threading
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.video_production import ProviderStageTask
from app.db_models import ProviderCostReservation
from app.domains.video_production.production_action_result import ProductionActionResult
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.production_observability.production_observability_service import record_production_event
from app.domains.video_production.production_queue_service import retry_job_without_attempt
from app.domains.video_production.production_state_contract import (
    COST_SUBMITTED,
    PROVIDER_TASK_CANCELLED,
    PROVIDER_TASK_FAILED,
    PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
    PROVIDER_TASK_RUNNING,
    PROVIDER_TASK_SUBMITTED,
    PROVIDER_TASK_SUCCEEDED,
    PROVIDER_TASK_SYNC_REQUIRED,
)
from app.domains.video_production.provider_capability_service import (
    DEFAULT_REAL_PROVIDER_CAPABILITY,
    assert_real_paid_allowed,
)
from app.domains.video_production.provider_cost_reservation_service import (
    create_cost_reservation,
    mark_reservation_submitted,
    mark_reservation_stale_needs_repair,
    settle_reservation,
)
from app.domains.video_production.provider_stage_task_service import (
    claim_stage_task_for_submit,
    get_or_create_stage_task,
    provider_stage_idempotency_key,
    request_hash,
    set_task_status,
)


COMPLETED_PROVIDER_STATUSES = {"succeeded", "completed", "done", "success"}
FAILED_PROVIDER_STATUSES = {"failed", "error"}
CANCELLED_PROVIDER_STATUSES = {"cancelled", "canceled"}
FAILED_PROVIDER_ASSET_STATUSES = FAILED_PROVIDER_STATUSES | CANCELLED_PROVIDER_STATUSES
DEFAULT_THROTTLE_RETRY_AFTER_SECONDS = 60
PROVIDER_SUBMIT_WORKER_COUNT_ENV = "DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT"
PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT = {
    "enforcement_scope": "single_process",
    "uses_process_local_lock": True,
    "uses_db_submit_claim": True,
    "cross_process_hard_quota": False,
    "requires_runtime_worker_count": True,
    "runtime_worker_count_env": PROVIDER_SUBMIT_WORKER_COUNT_ENV,
}
PROVIDER_THROTTLE_ACTIVE_STATUSES = {
    PROVIDER_TASK_SUBMITTED,
    PROVIDER_TASK_RUNNING,
    PROVIDER_TASK_SYNC_REQUIRED,
    "manual_repair_required",
}
_PROVIDER_STAGE_LOCKS: dict[tuple[str, str, str], threading.RLock] = {}
_PROVIDER_STAGE_LOCKS_GUARD = threading.Lock()


def _provider_stage_lock(provider: str, model_name: str, stage: str) -> threading.RLock:
    key = (provider, model_name, stage)
    with _PROVIDER_STAGE_LOCKS_GUARD:
        lock = _PROVIDER_STAGE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PROVIDER_STAGE_LOCKS[key] = lock
        return lock


def assert_paid_submit_deployment_safe(capability: dict) -> None:
    del capability
    raw_count = os.getenv(PROVIDER_SUBMIT_WORKER_COUNT_ENV)
    if raw_count is None:
        raise ProductionRepairableError(
            code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
            message="Paid provider submit requires DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT=1 for this first-slice throttle contract.",
            cause="provider_submit_worker_count_required",
            repair_action="Set DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT=1 for a single paid-submit worker process before enabling paid provider execution.",
            repair_route="/video-production",
            retryable=False,
        )
    try:
        worker_process_count = int(raw_count)
    except (TypeError, ValueError) as exc:
        raise ProductionRepairableError(
            code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
            message="Paid provider submit worker count must be explicitly set to 1.",
            cause="provider_submit_worker_count_required",
            repair_action="Set DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT=1 for this first-slice provider throttle contract.",
            repair_route="/video-production",
            retryable=False,
        ) from exc
    if worker_process_count != 1:
        raise ProductionRepairableError(
            code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
            message="Paid provider submit throttle is configured for multiple worker processes without a DB-backed cross-process quota.",
            cause="provider_cross_process_quota_required",
            repair_action="Run paid provider submits in a single worker process, or enable a DB-backed cross-process quota before increasing worker_process_count.",
            repair_route="/video-production",
            retryable=False,
        )


class ProviderStageExecutor:
    def __init__(self, client):
        self.client = client

    async def execute(
        self,
        db: Session,
        *,
        run_id: str,
        plan_id: str,
        job_id: str,
        target_type: str,
        target_id: str,
        stage: str,
        provider: str,
        model_name: str,
        estimated_cost: float,
        payload: dict,
        capability: dict | None = None,
    ) -> ProductionActionResult:
        resolved_capability = {**DEFAULT_REAL_PROVIDER_CAPABILITY, **(capability or {})}
        assert_real_paid_allowed(resolved_capability)
        _assert_positive_estimated_cost(estimated_cost)
        assert_paid_submit_deployment_safe(resolved_capability)

        with _provider_stage_lock(provider, model_name, stage):
            existing = _find_existing_task(
                db,
                run_id=run_id,
                stage=stage,
                target_type=target_type,
                target_id=target_id,
                provider=provider,
                model_name=model_name,
                payload=payload,
            )
            if _needs_submit_claim_repair(existing):
                _raise_submit_claim_repair_error(db, existing)
            if existing is None or not existing.provider_task_id:
                _assert_provider_capacity(
                    db,
                    job_id=job_id,
                    provider=provider,
                    model_name=model_name,
                    stage=stage,
                    max_concurrent_tasks=resolved_capability.get("max_concurrent_tasks"),
                )

            task, created = get_or_create_stage_task(
                db,
                run_id=run_id,
                plan_id=plan_id,
                job_id=job_id,
                target_type=target_type,
                target_id=target_id,
                stage=stage,
                provider=provider,
                model_name=model_name,
                payload=payload,
            )
            reservation = _reservation_for_task(db, task.id)
            if created:
                reservation = create_cost_reservation(
                    db,
                    plan_id=plan_id,
                    provider_stage_task_id=task.id,
                    estimated_cost=estimated_cost,
                )
            elif not task.provider_task_id and reservation is None:
                reservation = create_cost_reservation(
                    db,
                    plan_id=plan_id,
                    provider_stage_task_id=task.id,
                    estimated_cost=estimated_cost,
                )
            elif task.provider_task_id and reservation is None:
                _raise_missing_reservation_repair_error(task)
            task_id = task.id
            reservation_id = reservation.id if reservation else None
            provider_task_id = task.provider_task_id
            if provider_task_id:
                action = "sync"
            elif claim_stage_task_for_submit(db, task_id):
                action = "submit"
            else:
                task = _reload_task(db, task_id)
                provider_task_id = task.provider_task_id
                if provider_task_id:
                    action = "sync"
                else:
                    _close_transaction(db)
                    _raise_submit_claim_repair_error(db, task)
            _close_transaction(db)

        if action == "sync":
            sync_result = await self.client.sync(provider_task_id)
        else:
            try:
                submit_payload = _submit_payload_with_external_task(payload, task_id=task_id)
                submit_result = await self.client.submit(submit_payload)
                provider_task_id = _provider_task_id(submit_result)
            except ProductionRepairableError as exc:
                _record_provider_submit_failure(db, task_id, reservation_id, exc)
                raise
            except Exception as exc:
                repairable = ProductionRepairableError(
                    code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
                    message="Provider submit failed before returning a task id.",
                    cause="provider_submit_failed",
                    repair_action="Inspect the provider submission result and reconcile the provider stage task before retrying.",
                    repair_route="/video-production",
                    retryable=True,
                    affected_ids=[task_id],
                )
                _record_provider_submit_failure(db, task_id, reservation_id, repairable, raw_error=exc)
                raise repairable from exc
            task = _reload_task(db, task_id)
            task = set_task_status(
                db,
                task,
                PROVIDER_TASK_SUBMITTED,
                provider_task_id=provider_task_id,
                external_task_id=submit_result.get("external_task_id") or task_id,
                response_summary_json=submit_result,
                submitted_at=bj_now(),
            )
            reservation = _reservation_for_task(db, task_id)
            if reservation and reservation.status != COST_SUBMITTED:
                reservation = mark_reservation_submitted(db, reservation.id)
            _close_transaction(db)
            sync_result = await self.client.sync(provider_task_id)

        task = _reload_task(db, task_id)
        reservation = _reload_reservation(db, reservation_id)
        if resolved_capability.get("settle_missing_usage_with_estimated_cost") is True:
            sync_result = _sync_result_with_estimated_usage(sync_result, estimated_cost)
        return _handle_sync_result(
            db,
            task=task,
            reservation=reservation,
            run_id=run_id,
            plan_id=plan_id,
            target_type=target_type,
            target_id=target_id,
            stage=stage,
            provider=provider,
            model_name=model_name,
            estimated_cost=estimated_cost,
            sync_result=sync_result,
        )


def _assert_positive_estimated_cost(estimated_cost: float) -> None:
    try:
        amount = float(estimated_cost)
    except (TypeError, ValueError) as exc:
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_BLOCKED,
            message="Paid provider submit requires a positive estimated_cost before reservation.",
            cause="provider_estimated_cost_missing",
            repair_action="Configure a positive estimated_cost for the selected paid provider model before running this stage.",
            repair_route="/video-production",
            retryable=False,
        ) from exc
    if amount <= 0:
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_BLOCKED,
            message="Paid provider submit requires a positive estimated_cost before reservation.",
            cause="provider_estimated_cost_missing",
            repair_action="Configure a positive estimated_cost for the selected paid provider model before running this stage.",
            repair_route="/video-production",
            retryable=False,
        )


def _submit_payload_with_external_task(payload: dict, *, task_id: str) -> dict:
    submit_payload = dict(payload)
    submit_payload["external_task_id"] = task_id
    submit_payload["provider_stage_task_id"] = task_id
    submit_payload["provider_idempotency_key"] = submit_payload.get("provider_idempotency_key") or task_id
    return submit_payload


def _find_existing_task(
    db: Session,
    *,
    run_id: str,
    stage: str,
    target_type: str,
    target_id: str,
    provider: str,
    model_name: str,
    payload: dict,
) -> ProviderStageTask | None:
    idempotency_key = provider_stage_idempotency_key(
        run_id=run_id,
        stage=stage,
        target_type=target_type,
        target_id=target_id,
        provider=provider,
        model_name=model_name,
    )
    existing = db.query(ProviderStageTask).filter_by(idempotency_key=idempotency_key).first()
    if existing and existing.request_hash != request_hash(payload):
        raise ValueError("Provider stage task idempotency key reused with a different request hash")
    return existing


def _needs_submit_claim_repair(task: ProviderStageTask | None) -> bool:
    return (
        task is not None
        and task.provider_task_id is None
        and task.status in {PROVIDER_TASK_SUBMITTED, PROVIDER_TASK_SYNC_REQUIRED}
    )


def _raise_submit_claim_repair_error(db: Session, task: ProviderStageTask) -> None:
    reservation = _reservation_for_task(db, task.id)
    error = ProductionRepairableError(
        code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
        message="Provider stage task was marked submitted without a provider task id.",
        cause="provider_task_id_missing_after_submit_claim",
        repair_action="Reconcile the provider stage task and stale reservation before retrying paid provider submit.",
        repair_route="/video-production",
        retryable=True,
        affected_ids=[task.id],
    )
    _record_provider_submit_failure(db, task.id, reservation.id if reservation else None, error)
    raise error


def _raise_missing_reservation_repair_error(task: ProviderStageTask) -> None:
    raise ProductionRepairableError(
        code=ProductionErrorCode.BUDGET_BLOCKED,
        message="Provider stage task has a provider task id but no cost reservation.",
        cause="provider_cost_reservation_missing",
        repair_action="Reconcile or create the provider cost reservation before syncing this paid provider task.",
        repair_route="/video-production",
        retryable=True,
        affected_ids=[task.id],
    )


def _assert_provider_capacity(
    db: Session,
    *,
    job_id: str,
    provider: str,
    model_name: str,
    stage: str,
    max_concurrent_tasks: Any,
) -> None:
    if max_concurrent_tasks is None:
        return
    limit = int(max_concurrent_tasks)
    if limit <= 0:
        return
    active_count = (
        db.query(func.count(ProviderStageTask.id))
        .filter(
            ProviderStageTask.provider == provider,
            ProviderStageTask.model_name == model_name,
            ProviderStageTask.stage == stage,
            ProviderStageTask.status.in_(PROVIDER_THROTTLE_ACTIVE_STATUSES),
        )
        .filter(
            (ProviderStageTask.status != PROVIDER_TASK_MANUAL_REPAIR_REQUIRED)
            | (ProviderStageTask.provider_task_id.isnot(None))
        )
        .scalar()
    )
    if int(active_count or 0) < limit:
        return

    retry_job_without_attempt(
        db,
        job_id,
        ProductionErrorCode.PROVIDER_THROTTLED.value,
        "Provider concurrency limit reached for this model and stage.",
        retry_after_seconds=DEFAULT_THROTTLE_RETRY_AFTER_SECONDS,
    )
    raise ProductionRepairableError(
        code=ProductionErrorCode.PROVIDER_THROTTLED,
        message="Provider concurrency limit reached for this model and stage.",
        cause="provider_stage_throttled",
        repair_action="Retry this provider stage after the throttle window.",
        repair_route="/video-production",
        retryable=True,
        affected_ids=[job_id],
    )


def _reservation_for_task(db: Session, task_id: str) -> ProviderCostReservation | None:
    return (
        db.query(ProviderCostReservation)
        .filter(ProviderCostReservation.provider_stage_task_id == task_id)
        .first()
    )


def _reload_task(db: Session, task_id: str) -> ProviderStageTask:
    task = db.query(ProviderStageTask).filter(ProviderStageTask.id == task_id).first()
    if not task:
        raise ValueError("Provider stage task not found")
    return task


def _reload_reservation(db: Session, reservation_id: str | None) -> ProviderCostReservation | None:
    if not reservation_id:
        return None
    return db.query(ProviderCostReservation).filter(ProviderCostReservation.id == reservation_id).first()


def _close_transaction(db: Session) -> None:
    if db.in_transaction():
        db.commit()


def _provider_task_id(submit_result: dict) -> str:
    provider_task_id = submit_result.get("provider_task_id") or submit_result.get("task_id") or submit_result.get("id")
    if not provider_task_id:
        raise ProductionRepairableError(
            code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
            message="Provider submit response did not include a task id.",
            cause="provider_task_id_missing",
            repair_action="Inspect provider submit response and retry with a supported provider.",
            repair_route="/video-production",
            retryable=True,
        )
    return str(provider_task_id)


def _record_provider_submit_failure(
    db: Session,
    task_id: str,
    reservation_id: str | None,
    error: ProductionRepairableError,
    *,
    raw_error: Exception | None = None,
) -> None:
    if db.in_transaction():
        db.rollback()
    message = str(raw_error) if raw_error is not None else error.message
    task = _reload_task(db, task_id)
    set_task_status(
        db,
        task,
        PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
        error_code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED.value,
        error_message=message,
        response_summary_json={
            "cause": error.cause or "provider_submit_failed",
            "message": message,
        },
    )
    if reservation_id:
        mark_reservation_stale_needs_repair(db, reservation_id)


def _handle_sync_result(
    db: Session,
    *,
    task: ProviderStageTask,
    reservation: ProviderCostReservation | None,
    run_id: str,
    plan_id: str,
    target_type: str,
    target_id: str,
    stage: str,
    provider: str,
    model_name: str,
    estimated_cost: float,
    sync_result: dict,
) -> ProductionActionResult:
    provider_status = str(sync_result.get("status") or "").lower()
    if provider_status in COMPLETED_PROVIDER_STATUSES:
        failed_assets = _failed_provider_assets(sync_result)
        if failed_assets:
            failure_result = {
                **sync_result,
                "status": "failed",
                "failed_assets": failed_assets,
            }
            if _is_retryable_quota_failure(sync_result, failed_assets):
                task = _mark_terminal_provider_failure(
                    db,
                    task,
                    failure_result,
                    PROVIDER_TASK_FAILED,
                    error_code=ProductionErrorCode.PROVIDER_THROTTLED.value,
                    archive_idempotency_key=True,
                )
                if reservation:
                    mark_reservation_stale_needs_repair(db, reservation.id)
                return ProductionActionResult.blocked(
                    ProductionErrorCode.PROVIDER_THROTTLED,
                    "服务商额度不足或限流，本阶段暂时无法产出资产。",
                    "补充服务商额度或等待限流窗口后重试；系统会保留本次生产任务并重新提交该阶段。",
                    repair_route="/video-production",
                    affected_ids=[task.id],
                    retryable=True,
                    data={
                        "provider_result": failure_result,
                        "provider_stage_task_id": task.id,
                    },
                )
            task = _mark_terminal_provider_failure(db, task, failure_result, PROVIDER_TASK_FAILED)
            if reservation:
                mark_reservation_stale_needs_repair(db, reservation.id)
            return ProductionActionResult.blocked(
                ProductionErrorCode.PROVIDER_TASK_FAILED,
                "Provider stage task completed with failed assets.",
                "Inspect the failed provider assets and retry through the explicit stage retry path so a new provider task and idempotency key are created.",
                repair_route="/video-production",
                affected_ids=[task.id],
                retryable=False,
                data={
                    "provider_result": failure_result,
                    "provider_stage_task_id": task.id,
                },
            )
        task = _mark_succeeded(db, task, sync_result)
        if reservation:
            usage = sync_result.get("usage") if isinstance(sync_result.get("usage"), dict) else {}
            actual_cost = _actual_cost_from_usage(db, task, reservation, usage)
            units_json = usage.get("units", {})
            settle_reservation(
                db,
                reservation.id,
                actual_cost=actual_cost,
                units_json=units_json,
            )
        record_production_event(
            db,
            event_type="provider_stage.succeeded",
            run_id=run_id,
            production_plan_id=plan_id,
            production_segment_id=target_id if target_type == "production_segment" else None,
            provider_task_id=task.provider_task_id,
            payload={
                "provider_stage_task_id": task.id,
                "stage": stage,
                "provider": provider,
                "model_name": model_name,
                "target_type": target_type,
                "target_id": target_id,
            },
        )
        db.commit()
        return ProductionActionResult.success(
            "Provider stage task succeeded.",
            data={
                "provider_result": sync_result,
                "provider_stage_task_id": task.id,
            },
        )

    if provider_status in FAILED_PROVIDER_STATUSES | CANCELLED_PROVIDER_STATUSES:
        terminal_status = (
            PROVIDER_TASK_CANCELLED
            if provider_status in CANCELLED_PROVIDER_STATUSES
            else PROVIDER_TASK_FAILED
        )
        if terminal_status == PROVIDER_TASK_FAILED and _is_retryable_quota_failure(sync_result):
            task = _mark_terminal_provider_failure(
                db,
                task,
                sync_result,
                terminal_status,
                error_code=ProductionErrorCode.PROVIDER_THROTTLED.value,
                archive_idempotency_key=True,
            )
            if reservation:
                mark_reservation_stale_needs_repair(db, reservation.id)
            return ProductionActionResult.blocked(
                ProductionErrorCode.PROVIDER_THROTTLED,
                "服务商额度不足或限流，本阶段暂时无法产出资产。",
                "补充服务商额度或等待限流窗口后重试；系统会保留本次生产任务并重新提交该阶段。",
                repair_route="/video-production",
                affected_ids=[task.id],
                retryable=True,
                data={
                    "provider_result": sync_result,
                    "provider_stage_task_id": task.id,
                },
            )
        task = _mark_terminal_provider_failure(db, task, sync_result, terminal_status)
        if reservation:
            mark_reservation_stale_needs_repair(db, reservation.id)
        return ProductionActionResult.blocked(
            ProductionErrorCode.PROVIDER_TASK_FAILED,
            "Provider stage task ended without a successful provider result.",
            "Inspect the provider task failure and regenerate or retry through the explicit stage retry path so a new provider task and idempotency key are created.",
            repair_route="/video-production",
            affected_ids=[task.id],
            retryable=False,
            data={
                "provider_result": sync_result,
                "provider_stage_task_id": task.id,
            },
        )

    task = _mark_sync_required(db, task, sync_result)
    return _sync_required_result(task.id)


def _failed_provider_assets(sync_result: dict) -> list[dict]:
    assets = sync_result.get("assets")
    if not isinstance(assets, list):
        return []
    failed = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        status = str(asset.get("status") or "").lower()
        if status in FAILED_PROVIDER_ASSET_STATUSES:
            failed.append(asset)
    return failed


def _is_retryable_quota_failure(sync_result: dict, failed_assets: list[dict] | None = None) -> bool:
    payloads: list[dict] = [sync_result]
    if failed_assets is not None:
        payloads.extend(failed_assets)
    else:
        assets = sync_result.get("assets")
        if isinstance(assets, list):
            payloads.extend([asset for asset in assets if isinstance(asset, dict)])

    retryable_seen = False
    text_parts: list[str] = []
    for payload in payloads:
        retryable_seen = retryable_seen or payload.get("retryable") is True
        for key in ("error_code", "error", "message", "cause"):
            value = payload.get(key)
            if value is not None:
                text_parts.append(str(value))

    text = " ".join(text_parts).lower()
    quota_seen = any(token in text for token in ("429", "quota", "rate limit", "rate_limit", "throttle", "限流", "额度"))
    return retryable_seen and quota_seen


def _actual_cost_from_usage(
    db: Session,
    task: ProviderStageTask,
    reservation: ProviderCostReservation,
    usage: dict,
) -> float:
    raw_cost = usage.get("actual_cost", usage.get("cost"))
    if raw_cost is None:
        mark_reservation_stale_needs_repair(db, reservation.id)
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_BLOCKED,
            message="Provider completed without usage.actual_cost or usage.cost; cost settlement requires manual repair.",
            cause="provider_usage_cost_missing",
            repair_action="Reconcile the provider usage and settle the cost reservation before continuing paid execution.",
            repair_route="/video-production",
            retryable=True,
            affected_ids=[task.id, reservation.id],
        )
    try:
        actual = float(raw_cost)
    except (TypeError, ValueError) as exc:
        mark_reservation_stale_needs_repair(db, reservation.id)
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_BLOCKED,
            message="Provider usage cost is not numeric; cost settlement requires manual repair.",
            cause="provider_usage_cost_invalid",
            repair_action="Reconcile the provider usage and settle the cost reservation before continuing paid execution.",
            repair_route="/video-production",
            retryable=True,
            affected_ids=[task.id, reservation.id],
        ) from exc
    if actual < 0:
        mark_reservation_stale_needs_repair(db, reservation.id)
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_BLOCKED,
            message="Provider usage cost cannot be negative; cost settlement requires manual repair.",
            cause="provider_usage_cost_invalid",
            repair_action="Reconcile the provider usage and settle the cost reservation before continuing paid execution.",
            repair_route="/video-production",
            retryable=True,
            affected_ids=[task.id, reservation.id],
        )
    return actual


def _sync_result_with_estimated_usage(sync_result: dict, estimated_cost: float) -> dict:
    usage = sync_result.get("usage") if isinstance(sync_result.get("usage"), dict) else {}
    if usage.get("actual_cost", usage.get("cost")) is not None:
        return sync_result
    return {
        **sync_result,
        "usage": {
            **usage,
            "actual_cost": float(estimated_cost or 0.0),
            "cost_source": "estimated_cost_fallback",
        },
    }


def _mark_task_sync_required_blocked(db: Session, task_id: str, response_summary: dict) -> ProductionActionResult:
    task = _reload_task(db, task_id)
    task = _mark_sync_required(db, task, response_summary)
    return _sync_required_result(task.id)


def _sync_required_result(task_id: str) -> ProductionActionResult:
    return ProductionActionResult.blocked(
        ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED,
        "Provider stage task still requires sync.",
        "Run provider task sync after the provider finishes the task.",
        repair_route="/video-production",
        affected_ids=[task_id],
        retryable=True,
    )


def _mark_succeeded(db: Session, task: ProviderStageTask, sync_result: dict) -> ProviderStageTask:
    if task.status == PROVIDER_TASK_SYNC_REQUIRED:
        task = set_task_status(db, task, PROVIDER_TASK_RUNNING, response_summary_json=sync_result)
    if task.status == PROVIDER_TASK_SUCCEEDED:
        task.response_summary_json = sync_result
        db.commit()
        db.refresh(task)
        return task
    return set_task_status(
        db,
        task,
        PROVIDER_TASK_SUCCEEDED,
        response_summary_json=sync_result,
        completed_at=bj_now(),
    )


def _mark_sync_required(db: Session, task: ProviderStageTask, sync_result: dict) -> ProviderStageTask:
    if task.status == PROVIDER_TASK_SYNC_REQUIRED:
        task.response_summary_json = sync_result
        db.commit()
        db.refresh(task)
        return task
    if task.status == "reserved":
        task = set_task_status(db, task, PROVIDER_TASK_SUBMITTED, response_summary_json=sync_result)
    return set_task_status(
        db,
        task,
        PROVIDER_TASK_SYNC_REQUIRED,
        response_summary_json=sync_result,
    )


def _mark_terminal_provider_failure(
    db: Session,
    task: ProviderStageTask,
    sync_result: dict,
    terminal_status: str,
    *,
    error_code: str | None = None,
    archive_idempotency_key: bool = False,
) -> ProviderStageTask:
    if task.status == terminal_status:
        task.response_summary_json = sync_result
        db.commit()
        db.refresh(task)
        return task
    message = str(sync_result.get("error") or sync_result.get("message") or "Provider task ended without success.")
    if archive_idempotency_key:
        task.idempotency_key = _archived_idempotency_key(task)
    return set_task_status(
        db,
        task,
        terminal_status,
        error_code=error_code or ProductionErrorCode.PROVIDER_TASK_FAILED.value,
        error_message=message,
        response_summary_json=sync_result,
        completed_at=bj_now(),
    )


def _archived_idempotency_key(task: ProviderStageTask) -> str:
    archived = f"{task.idempotency_key}:archived:{task.id}"
    if len(archived) <= 220:
        return archived
    digest = request_hash({"idempotency_key": task.idempotency_key})[:24]
    return f"archived:{task.id}:{digest}"
