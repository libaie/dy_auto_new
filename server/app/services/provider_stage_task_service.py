import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProviderStageTask
from app.services.production_state_contract import PROVIDER_TASK_RESERVED, PROVIDER_TASK_SUBMITTED, validate_transition


def request_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def provider_stage_idempotency_key(
    *,
    run_id: str,
    stage: str,
    target_type: str,
    target_id: str,
    provider: str,
    model_name: str,
) -> str:
    return f"{run_id}:{stage}:{target_type}:{target_id}:{provider}:{model_name}"


def get_or_create_stage_task(
    db: Session,
    *,
    run_id: str,
    plan_id: str,
    job_id: str | None,
    target_type: str,
    target_id: str,
    stage: str,
    provider: str,
    model_name: str,
    payload: dict,
) -> tuple[ProviderStageTask, bool]:
    digest = request_hash(payload)
    idempotency_key = provider_stage_idempotency_key(
        run_id=run_id,
        stage=stage,
        target_type=target_type,
        target_id=target_id,
        provider=provider,
        model_name=model_name,
    )
    existing = db.query(ProviderStageTask).filter_by(idempotency_key=idempotency_key).first()
    if existing:
        if existing.request_hash != digest:
            raise ValueError("Provider stage task idempotency key reused with a different request hash")
        return existing, False

    task = ProviderStageTask(
        run_id=run_id,
        plan_id=plan_id,
        job_id=job_id,
        target_type=target_type,
        target_id=target_id,
        stage=stage,
        provider=provider,
        model_name=model_name,
        request_hash=digest,
        idempotency_key=idempotency_key,
        status="reserved",
    )
    db.add(task)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProviderStageTask).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            if existing.request_hash != digest:
                raise ValueError("Provider stage task idempotency key reused with a different request hash")
            return existing, False
        raise
    db.refresh(task)
    return task, True


def set_task_status(db: Session, task: ProviderStageTask, next_status: str, **values) -> ProviderStageTask:
    if task.status != next_status and not validate_transition("provider_stage_task", task.status, next_status):
        raise ValueError(f"Invalid provider stage task transition: {task.status} -> {next_status}")
    for key, value in values.items():
        setattr(task, key, value)
    task.status = next_status
    task.updated_at = bj_now()
    db.commit()
    db.refresh(task)
    return task


def claim_stage_task_for_submit(db: Session, task_id: str) -> bool:
    now = bj_now()
    updated = (
        db.query(ProviderStageTask)
        .filter(
            ProviderStageTask.id == task_id,
            ProviderStageTask.status == PROVIDER_TASK_RESERVED,
            ProviderStageTask.provider_task_id.is_(None),
        )
        .update(
            {
                "status": PROVIDER_TASK_SUBMITTED,
                "submitted_at": now,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return updated == 1
