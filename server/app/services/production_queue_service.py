from datetime import datetime, timedelta

from sqlalchemy import case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProductionJob, ProductionPlan
from app.services.production_status import (
    JOB_BLOCKED,
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
    JOB_RUNNING,
    PLAN_READY,
    PLAN_RUNNING,
)

ACTIVE_PLAN_STATUSES = (PLAN_READY, PLAN_RUNNING)


def _active_plan_ids_query():
    return select(ProductionPlan.id).where(ProductionPlan.status.in_(ACTIVE_PLAN_STATUSES))


def _ensure_plan_accepts_jobs(db: Session, plan_id: str) -> None:
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Production plan not found")
    if plan.status not in ACTIVE_PLAN_STATUSES:
        raise ValueError("Production plan is not accepting jobs")


def enqueue_job(
    db: Session,
    plan_id: str,
    target_type: str,
    target_id: str,
    stage: str,
    idempotency_key: str,
    priority: int = 100,
    max_attempts: int = 3,
) -> ProductionJob:
    existing = db.query(ProductionJob).filter(ProductionJob.idempotency_key == idempotency_key).first()
    if existing:
        return existing
    _ensure_plan_accepts_jobs(db, plan_id)

    job = ProductionJob(
        plan_id=plan_id,
        target_type=target_type,
        target_id=target_id,
        stage=stage,
        status=JOB_QUEUED,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProductionJob).filter(ProductionJob.idempotency_key == idempotency_key).first()
        if existing:
            return existing
        raise
    db.refresh(job)
    return job


def claim_next_job(
    db: Session,
    lease_id: str,
    lease_seconds: int = 300,
    *,
    plan_id: str | None = None,
    stage: str | None = None,
) -> ProductionJob | None:
    skipped_ids: set[str] = set()
    while True:
        now = bj_now()
        query = (
            db.query(ProductionJob)
            .filter(ProductionJob.plan_id.in_(_active_plan_ids_query()))
            .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
            .filter((ProductionJob.retry_after.is_(None)) | (ProductionJob.retry_after <= now))
            .filter(ProductionJob.scheduled_at <= now)
        )
        if plan_id:
            query = query.filter(ProductionJob.plan_id == plan_id)
        if stage:
            query = query.filter(ProductionJob.stage == stage)
        if skipped_ids:
            query = query.filter(~ProductionJob.id.in_(skipped_ids))
        job = query.order_by(
            ProductionJob.priority.asc(), ProductionJob.scheduled_at.asc(), ProductionJob.created_at.asc()
        ).first()
        if not job:
            return None

        update_query = (
            db.query(ProductionJob)
            .filter(ProductionJob.id == job.id)
            .filter(ProductionJob.plan_id.in_(_active_plan_ids_query()))
            .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
            .filter((ProductionJob.retry_after.is_(None)) | (ProductionJob.retry_after <= now))
            .filter(ProductionJob.scheduled_at <= now)
        )
        if plan_id:
            update_query = update_query.filter(ProductionJob.plan_id == plan_id)
        if stage:
            update_query = update_query.filter(ProductionJob.stage == stage)
        # Persist the exact claim token at MySQL DATETIME's supported precision.
        claim_lease = (lease_id, (now + timedelta(seconds=lease_seconds)).replace(microsecond=0))
        updated = update_query.update(
            {
                "status": JOB_LEASED,
                "lease_id": lease_id,
                "leased_until": claim_lease[1],
                "updated_at": now,
            },
            synchronize_session=False,
        )
        db.commit()
        if not updated:
            skipped_ids.add(job.id)
            continue

        db.refresh(job)
        # ORM refresh may already see a replacement; it must not redefine ownership.
        job._production_claim_lease = claim_lease
        return job


def release_expired_leases(db: Session, *, plan_id: str | None = None) -> int:
    now = bj_now()
    query = db.query(ProductionJob).filter(
        ProductionJob.status.in_((JOB_LEASED, JOB_RUNNING)), ProductionJob.leased_until <= now,
    )
    if plan_id is not None:
        query = query.filter(ProductionJob.plan_id == plan_id)
    count = query.update(
        {"status": JOB_QUEUED, "lease_id": None, "leased_until": None, "updated_at": now},
        synchronize_session=False,
    )
    db.commit()
    return count


def mark_job_completed(
    db: Session,
    job_id: str,
    *,
    provider_task_id: str | None = None,
    payload: dict | None = None,
    allowed_statuses: tuple[str, ...] | list[str] | None = None,
    expected_lease_id: str | None = None,
    expected_leased_until: datetime | None = None,
) -> ProductionJob:
    del payload
    default_allowed = (JOB_LEASED, JOB_RUNNING)
    explicitly_allowed = (JOB_QUEUED, JOB_LEASED, JOB_RUNNING)
    if allowed_statuses is None:
        allowed = default_allowed
    else:
        requested = tuple(allowed_statuses)
        illegal = set(requested) - set(explicitly_allowed)
        if illegal:
            db.rollback()
            raise ValueError("Production job cannot be completed from unauthorized allowed_statuses")
        allowed = requested

    now = bj_now()
    values = {
        "status": JOB_COMPLETED,
        "completed_at": now,
        "updated_at": now,
        "lease_id": None,
        "leased_until": None,
        "retry_after": None,
    }
    if provider_task_id is not None:
        values["provider_task_id"] = provider_task_id

    update_query = (
        db.query(ProductionJob)
        .filter(ProductionJob.id == job_id)
        .filter(ProductionJob.status.in_(allowed))
    )
    update_query = _fence_lease(update_query, expected_lease_id, expected_leased_until, now)
    updated = update_query.update(values, synchronize_session=False)
    if updated == 1:
        db.commit()
        job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
        if not job:
            raise ValueError("Production job not found")
        db.refresh(job)
        return job

    db.rollback()
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise ValueError("Production job not found")
    if job.status == JOB_COMPLETED and expected_lease_id is None:
        return job
    if job.status in (JOB_BLOCKED, JOB_FAILED, JOB_CANCELLED):
        raise ValueError("Production job cannot be completed from terminal or blocked status")
    raise ValueError("Production job cannot be completed from current status")


def _fence_lease(query, expected_lease_id, expected_leased_until, now):
    if expected_lease_id is not None:
        query = query.filter(
            ProductionJob.lease_id == expected_lease_id,
            ProductionJob.status.in_((JOB_LEASED, JOB_RUNNING)),
            ProductionJob.leased_until > now,
        )
    if expected_leased_until is not None:
        query = query.filter(ProductionJob.leased_until == expected_leased_until)
    return query


def _write_job_transition(db, job_id, values, expected_lease_id, expected_leased_until):
    query = db.query(ProductionJob).filter(
        ProductionJob.id == job_id,
        ProductionJob.status.in_((JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT)),
    )
    query = _fence_lease(query, expected_lease_id, expected_leased_until, bj_now())
    updated = query.update(values, synchronize_session=False)
    if updated != 1:
        db.rollback()
        raise ValueError("Production job lease or status does not match")
    db.commit()
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).one()
    db.refresh(job)
    return job


def fail_job(
    db: Session,
    job_id: str,
    error_code: str,
    error_message: str,
    retryable: bool,
    retry_after_seconds: int = 60,
    *,
    expected_lease_id: str | None = None,
    expected_leased_until: datetime | None = None,
) -> ProductionJob:
    now = bj_now()
    can_retry = (ProductionJob.attempt_count + 1 < ProductionJob.max_attempts) if retryable else False
    return _write_job_transition(db, job_id, {
        "attempt_count": ProductionJob.attempt_count + 1,
        "error_code": error_code,
        "error_message": error_message,
        "retryable": retryable,
        "status": case((can_retry, JOB_RETRY_WAIT), else_=JOB_FAILED),
        "retry_after": case((can_retry, now + timedelta(seconds=retry_after_seconds)), else_=None),
        "lease_id": None,
        "leased_until": None,
        "updated_at": now,
    }, expected_lease_id, expected_leased_until)


def retry_job_without_attempt(
    db: Session,
    job_id: str,
    error_code: str,
    error_message: str,
    *,
    retry_after_seconds: int = 60,
    expected_lease_id: str | None = None,
    expected_leased_until: datetime | None = None,
) -> ProductionJob:
    now = bj_now()
    return _write_job_transition(db, job_id, {
        "status": JOB_RETRY_WAIT,
        "error_code": error_code,
        "error_message": error_message,
        "retryable": True,
        "retry_after": now + timedelta(seconds=retry_after_seconds),
        "lease_id": None,
        "leased_until": None,
        "updated_at": now,
    }, expected_lease_id, expected_leased_until)


def pause_plan_jobs(db: Session, plan_id: str, reason: str) -> int:
    now = bj_now()
    jobs = db.query(ProductionJob).filter(
        ProductionJob.plan_id == plan_id,
        ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]),
    ).all()
    for job in jobs:
        job.resume_status = job.status
        job.status = JOB_BLOCKED
        job.blocked_reason = reason
        job.error_code = reason
        job.paused_at = now
        job.updated_at = now
    db.commit()
    return len(jobs)


def resume_plan_jobs(db: Session, plan_id: str) -> int:
    now = bj_now()
    jobs = db.query(ProductionJob).filter(
        ProductionJob.plan_id == plan_id,
        ProductionJob.status == JOB_BLOCKED,
        ProductionJob.resume_status.isnot(None),
    ).all()
    for job in jobs:
        job.status = job.resume_status
        job.resume_status = None
        job.blocked_reason = None
        job.paused_at = None
        job.updated_at = now
    db.commit()
    return len(jobs)
