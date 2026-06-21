"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 provider_stage_task_service 相关业务规则、状态转换和外部系统边界。
"""

import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.video_production import ProviderStageTask
from app.domains.video_production.production_state_contract import (
    PROVIDER_TASK_RESERVED,
    PROVIDER_TASK_SUBMITTED,
    validate_transition,
)


def request_hash(payload: dict) -> str:
    """业务函数：处理 request_hash 对应的业务流程、校验或数据转换。"""
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
    """业务函数：处理 provider_stage_idempotency_key 对应的业务流程、校验或数据转换。"""
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
    """业务函数：处理 get_or_create_stage_task 对应的业务流程、校验或数据转换。"""
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
    """业务函数：处理 set_task_status 对应的业务流程、校验或数据转换。"""
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
    """业务函数：处理 claim_stage_task_for_submit 对应的业务流程、校验或数据转换。"""
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
