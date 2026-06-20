from __future__ import annotations

from sqlalchemy.orm import Session

from app.db_models import AgencyExpertInvocation, ProductionAuditEvent, ProductionJob, ProductionPlan
from app.domains.agency_operations.agency_repair_contracts import AUTO_REPAIR_STAGE, AutoRepairPolicy, RepairTask
from app.domains.video_production.production_status import JOB_BLOCKED, JOB_LEASED, JOB_QUEUED, JOB_RETRY_WAIT, JOB_RUNNING
from app.domains.video_production.provider_cost_reservation_service import active_reserved_cost


def enqueue_repair_tasks_for_invocation(
    db: Session,
    invocation: AgencyExpertInvocation,
    policy_snapshot: dict | None,
) -> dict:
    output = invocation.output_summary_json or {}
    tasks = [RepairTask.model_validate(item) for item in output.get("repair_tasks") or [] if isinstance(item, dict)]
    policy = AutoRepairPolicy.model_validate(policy_snapshot or {})
    result = {"created": 0, "deduped": 0, "manual_required": 0, "budget_reserved": 0.0}
    repair_budget_used = _repair_budget_used(db, invocation.production_plan_id, invocation.run_id)
    reserved_this_call = 0.0

    for task in tasks:
        repair_round = _next_repair_round(db, invocation, task)
        allowed, reason = _can_auto_execute(
            db,
            invocation,
            task,
            policy,
            repair_budget_used + reserved_this_call,
            repair_round,
        )
        if not allowed:
            _record_manual_required(db, invocation, task, reason, repair_round=repair_round)
            result["manual_required"] += 1
            continue

        job, created = _enqueue_repair_job(db, invocation, task, repair_round)
        if created:
            result["created"] += 1
            if task.requires_paid_provider:
                reserved_this_call += float(task.estimated_cost or 0.0)
                result["budget_reserved"] = round(result["budget_reserved"] + float(task.estimated_cost or 0.0), 4)
        else:
            result["deduped"] += 1

    return result


def _can_auto_execute(
    db: Session,
    invocation: AgencyExpertInvocation,
    task: RepairTask,
    policy: AutoRepairPolicy,
    repair_budget_used: float,
    repair_round: int,
) -> tuple[bool, str]:
    if not policy.enabled:
        return False, "自动返修策略未启用，需要人工确认"
    if not task.auto_execute:
        return False, "专家发现需要人工确认的问题"
    if task.stage not in set(policy.allowed_stages or []):
        return False, "当前阶段未授权自动返修"
    if task.type not in set(policy.allowed_types or []):
        return False, "当前返修类型未授权自动执行"
    if repair_round > int(policy.max_rounds or 0):
        return False, "自动返修轮数已达上限"
    if task.requires_paid_provider and repair_budget_used + float(task.estimated_cost or 0.0) > float(policy.budget_limit or 0.0):
        return False, "自动返修预算不足，需要人工确认是否继续付费返修"
    if task.requires_paid_provider and not _provider_budget_available(db, invocation.production_plan_id, float(task.estimated_cost or 0.0)):
        return False, "生产预算不足，需要人工确认是否继续付费返修"
    if task.requires_paid_provider:
        return False, "付费模型返修需要走成本预留路径，请去审查中心确认"
    return True, ""


def _provider_budget_available(db: Session, plan_id: str | None, estimated_cost: float) -> bool:
    if not plan_id:
        return False
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan or plan.budget_limit is None:
        return False
    return float(plan.current_cost or 0.0) + active_reserved_cost(db, plan_id) + estimated_cost <= float(plan.budget_limit)


def _repair_budget_used(db: Session, plan_id: str | None, run_id: str | None) -> float:
    if not plan_id:
        return 0.0
    query = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id == plan_id)
        .filter(ProductionAuditEvent.event_type == "agency_repair_task_created")
    )
    if run_id:
        query = query.filter(ProductionAuditEvent.run_id == run_id)
    total = 0.0
    for row in query.all():
        repair_task = ((row.payload_json or {}).get("repair_task") or {})
        if repair_task.get("requires_paid_provider"):
            total += float(repair_task.get("estimated_cost") or 0.0)
    return total


def _stable_repair_scope(invocation: AgencyExpertInvocation, task: RepairTask) -> tuple[str | None, str, str, str, str]:
    target = task.target_id or invocation.series_id or "missing-target"
    return (invocation.production_plan_id, task.stage, task.type, task.target_type, target)


def _next_repair_round(db: Session, invocation: AgencyExpertInvocation, task: RepairTask) -> int:
    scope = _stable_repair_scope(invocation, task)
    rows = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.event_type == "agency_repair_task_created")
        .filter(ProductionAuditEvent.production_plan_id == invocation.production_plan_id)
        .all()
    )
    previous = 0
    for row in rows:
        repair_task = ((row.payload_json or {}).get("repair_task") or {})
        row_scope = (
            row.production_plan_id,
            repair_task.get("stage"),
            repair_task.get("type"),
            repair_task.get("target_type"),
            repair_task.get("target_id") or invocation.series_id,
        )
        if row_scope == scope:
            previous += 1
    return previous + 1


def _existing_open_repair_job(db: Session, invocation: AgencyExpertInvocation, task: RepairTask) -> ProductionJob | None:
    return (
        db.query(ProductionJob)
        .filter(ProductionJob.plan_id == invocation.production_plan_id)
        .filter(ProductionJob.stage == f"{AUTO_REPAIR_STAGE}:{task.type}")
        .filter(ProductionJob.target_type == task.target_type)
        .filter(ProductionJob.target_id == (task.target_id or invocation.series_id))
        .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT, JOB_BLOCKED]))
        .first()
    )


def _enqueue_repair_job(
    db: Session,
    invocation: AgencyExpertInvocation,
    task: RepairTask,
    repair_round: int,
) -> tuple[ProductionJob, bool]:
    existing = _existing_open_repair_job(db, invocation, task)
    if existing:
        return existing, False
    idempotency_key = _idempotency_key(invocation, task, repair_round)
    existing = db.query(ProductionJob).filter(ProductionJob.idempotency_key == idempotency_key).first()
    if existing:
        return existing, False
    job = ProductionJob(
        plan_id=invocation.production_plan_id,
        target_type=task.target_type,
        target_id=task.target_id or invocation.series_id,
        stage=f"{AUTO_REPAIR_STAGE}:{task.type}",
        status=JOB_QUEUED,
        priority=10 if task.priority == "high" else 50,
        max_attempts=2,
        idempotency_key=idempotency_key,
        blocked_reason=(task.reason or "")[:120],
    )
    db.add(job)
    db.flush()
    db.add(ProductionAuditEvent(
        event_type="agency_repair_task_created",
        run_id=invocation.run_id,
        production_plan_id=invocation.production_plan_id,
        production_episode_id=invocation.production_episode_id,
        production_segment_id=invocation.production_segment_id,
        payload_json={
            "invocation_id": invocation.id,
            "repair_task": {**task.model_dump(), "round": repair_round},
            "job_id": job.id,
        },
    ))
    return job, True


def _record_manual_required(
    db: Session,
    invocation: AgencyExpertInvocation,
    task: RepairTask,
    reason: str,
    *,
    repair_round: int,
) -> None:
    db.add(ProductionAuditEvent(
        event_type="agency_repair_manual_required",
        run_id=invocation.run_id,
        production_plan_id=invocation.production_plan_id,
        production_episode_id=invocation.production_episode_id,
        production_segment_id=invocation.production_segment_id,
        payload_json={
            "invocation_id": invocation.id,
            "job_id": None,
            "reason": reason,
            "repair_task": {**task.model_dump(), "round": repair_round},
            "repair_action_label": task.repair_action_label or "联系人工处理",
            "repair_route": task.repair_route,
            "affected_ids": task.affected_ids,
        },
    ))


def _idempotency_key(invocation: AgencyExpertInvocation, task: RepairTask, repair_round: int) -> str:
    plan_id, stage, repair_type, target_type, target = _stable_repair_scope(invocation, task)
    return f"repair:{plan_id}:{stage}:{repair_type}:{target_type}:{target}:round:{repair_round}"
