from __future__ import annotations

import re

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.models.agency_operations import AgencyCreativePatch, AgencyExpertInvocation
from app.db_models import ProductionAuditEvent, ProductionJob, ProductionPlan, VideoProductionRun
from app.deps import require_role, verify_admin_token
from app.domains.agency_operations.agency_creative_patch_service import (
    apply_approved_patches,
    apply_patch as apply_creative_patch,
    approve_patch as approve_creative_patch,
    creative_patch_summary,
    reject_patch as reject_creative_patch,
    update_patch_after,
)
from app.domains.agency_operations.agency_manifest import (
    AgencyManifestError,
    get_expert,
    get_legacy_expert,
    list_experts,
    load_manifest,
    read_expert_markdown,
    read_legacy_expert_markdown,
)
from app.domains.production_observability.production_observability_service import _redact as _redact_secret_fields
from app.domains.video_production.production_status import JOB_BLOCKED, JOB_FAILED, JOB_QUEUED, JOB_RETRY_WAIT
from app.domains.video_production.provider_cost_reservation_service import active_reserved_cost

router = APIRouter(prefix="/api/agency", tags=["agency"])

_EXPERT_ID_RE = re.compile(r"^[a-z0-9_]+$")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]+|sk-[a-z0-9._-]{8,}|api[_-]?key\s*[:=]|authorization\s*[:=])"
)
_REPAIR_AUDIT_EVENT_TYPES = (
    "agency_repair_task_created",
    "agency_repair_manual_required",
    "agency_repair_completed",
    "agency_repair_failed",
    "agency_repair_recheck_required",
)


def _expert_summary(expert) -> dict:
    manifest = load_manifest()
    return {
        "expert_id": expert.expert_id,
        "name": expert.name_zh,
        "role_type": expert.role_type,
        "source_path": expert.source_path,
        "source_commit": manifest.source_commit,
        "sha256": expert.sha256,
        "phases": expert.phases,
        "legacy": False,
    }


def _legacy_expert_summary(expert) -> dict:
    return {
        "expert_id": expert.expert_id,
        "name": expert.name_zh,
        "role_type": expert.role_type,
        "source_path": expert.source_path,
        "source_commit": "legacy",
        "sha256": expert.sha256 or "",
        "phases": expert.phases,
        "legacy": True,
    }


def _invocation_summary(row: AgencyExpertInvocation) -> dict:
    output = row.output_summary_json or {}
    return {
        "id": row.id,
        "stage": row.stage,
        "expert_id": row.expert_id,
        "role": row.role,
        "execution_status": row.execution_status,
        "result_status": row.result_status,
        "summary": output.get("decision") or output.get("summary") or "",
        "duration_ms": row.duration_ms,
        "error_code": row.error_code,
    }


def _creative_patch_item(row: AgencyCreativePatch) -> dict:
    return {
        "id": row.id,
        "series_id": row.series_id,
        "episode_id": row.episode_id,
        "run_id": row.run_id,
        "stage": row.stage,
        "expert_id": row.expert_id,
        "patch_type": row.patch_type,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "title": row.title,
        "reason": row.reason,
        "before": row.before_json or {},
        "after": row.after_json or {},
        "status": row.status,
        "priority": row.priority,
        "source_invocation_id": row.source_invocation_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _redact_secret_values(value):
    if isinstance(value, dict):
        return {key: _redact_secret_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_secret_values(item) for item in value]
    if isinstance(value, str) and _SECRET_VALUE_RE.search(value):
        return "[REDACTED]"
    return value


def _redact_model_config_snapshot(snapshot: dict | None) -> dict:
    return _redact_secret_values(_redact_secret_fields(snapshot or {}))


@router.get("/experts")
def get_agency_experts(_=Depends(verify_admin_token)):
    return {"experts": [_expert_summary(expert) for expert in list_experts()]}


@router.get("/experts/{expert_id}")
def get_agency_expert(expert_id: str, _=Depends(require_role("admin"))):
    if not _EXPERT_ID_RE.fullmatch(expert_id):
        raise HTTPException(status_code=400, detail="专家标识无效")
    try:
        expert = get_expert(expert_id)
        data = _expert_summary(expert)
        data["markdown"] = read_expert_markdown(expert_id)
        return data
    except AgencyManifestError:
        try:
            legacy = get_legacy_expert(expert_id)
            data = _legacy_expert_summary(legacy)
            legacy_markdown = read_legacy_expert_markdown(expert_id)
            data["markdown"] = (
                "# 历史审计角色\n\n"
                "这是历史审计记录，不参与当前编排。\n\n"
                f"{legacy_markdown}"
            )
            return data
        except AgencyManifestError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/invocations")
def list_invocations(
    series_id: str | None = None,
    run_id: str | None = None,
    stage: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    query = db.query(AgencyExpertInvocation)
    if series_id:
        query = query.filter(AgencyExpertInvocation.series_id == series_id)
    if run_id:
        query = query.filter(or_(
            AgencyExpertInvocation.run_id == run_id,
            AgencyExpertInvocation.pipeline_run_id == run_id,
        ))
    if stage:
        query = query.filter(AgencyExpertInvocation.stage == stage)
    if status:
        query = query.filter(or_(
            AgencyExpertInvocation.execution_status == status,
            AgencyExpertInvocation.result_status == status,
        ))

    total = query.count()
    rows = (
        query.order_by(AgencyExpertInvocation.created_at.desc(), AgencyExpertInvocation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_invocation_summary(row) for row in rows],
    }


@router.get("/invocations/{invocation_id}")
def get_invocation(invocation_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    row = db.query(AgencyExpertInvocation).filter(AgencyExpertInvocation.id == invocation_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="专家调用记录不存在")
    return {
        **_invocation_summary(row),
        "input_summary": row.input_summary_json or {},
        "output_summary": row.output_summary_json or {},
        "evidence": row.evidence_json or [],
        "source_repo": row.source_repo,
        "source_commit": row.source_commit,
        "source_path": row.source_path,
        "source_sha256": row.source_sha256,
        "model_config_snapshot": _redact_model_config_snapshot(row.model_config_snapshot_json),
        "token_usage": row.token_usage_json or {},
        "error_message": row.error_message,
        "repair_action": row.repair_action,
        "repair_route": row.repair_route,
        "repair_target_type": row.repair_target_type,
        "repair_target_ids": row.repair_target_ids_json or [],
        "retry_scope": row.retry_scope,
    }


@router.get("/creative-patches")
def list_creative_patches(
    series_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    query = db.query(AgencyCreativePatch)
    if series_id:
        query = query.filter(AgencyCreativePatch.series_id == series_id)
    if run_id:
        query = query.filter(AgencyCreativePatch.run_id == run_id)
    if status:
        query = query.filter(AgencyCreativePatch.status == status)
    if stage:
        query = query.filter(AgencyCreativePatch.stage == stage)
    if target_type:
        query = query.filter(AgencyCreativePatch.target_type == target_type)
    if target_id:
        query = query.filter(AgencyCreativePatch.target_id == target_id)
    rows = query.order_by(AgencyCreativePatch.created_at.desc(), AgencyCreativePatch.id.desc()).all()
    return {
        "summary": creative_patch_summary(db, series_id=series_id, run_id=run_id),
        "items": [_creative_patch_item(row) for row in rows],
    }


@router.patch("/creative-patches/{patch_id}")
def update_creative_patch(
    patch_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    after = body.get("after")
    if not isinstance(after, dict):
        raise HTTPException(status_code=422, detail="必须提供 after 改稿内容")
    try:
        row = update_patch_after(db, patch_id, after, reviewer_user_id=user[0] if isinstance(user, tuple) else None)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _creative_patch_item(row)


@router.post("/creative-patches/{patch_id}/approve")
def approve_creative_patch_route(
    patch_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        row = approve_creative_patch(db, patch_id, reviewer_user_id=user[0] if isinstance(user, tuple) else None)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _creative_patch_item(row)


@router.post("/creative-patches/{patch_id}/reject")
def reject_creative_patch_route(
    patch_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="必须填写拒绝原因")
    try:
        row = reject_creative_patch(db, patch_id, reason=reason, reviewer_user_id=user[0] if isinstance(user, tuple) else None)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _creative_patch_item(row)


@router.post("/creative-patches/{patch_id}/apply")
def apply_creative_patch_route(
    patch_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        return apply_creative_patch(db, patch_id, reviewer_user_id=user[0] if isinstance(user, tuple) else None)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/creative-patches/apply-approved")
def apply_approved_creative_patches_route(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    return apply_approved_patches(
        db,
        run_id=body.get("run_id"),
        series_id=body.get("series_id"),
        stage=body.get("stage"),
        reviewer_user_id=user[0] if isinstance(user, tuple) else None,
    )


@router.post("/assets/{asset_id}/multimodal-review")
async def run_asset_multimodal_review(
    asset_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    from app.domains.agency_operations.agency_multimodal_review import run_multimodal_asset_review

    trace = await run_multimodal_asset_review(db, asset_id)
    return {"ok": True, "trace": trace}


@router.get("/repair-tasks")
def list_repair_tasks(
    series_id: str | None = None,
    run_id: str | None = None,
    stage: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    query = db.query(ProductionJob).filter(ProductionJob.stage.like("agency_auto_repair%"))
    if series_id:
        query = query.join(ProductionPlan, ProductionPlan.id == ProductionJob.plan_id).filter(ProductionPlan.series_id == series_id)
    if stage:
        query = query.filter(ProductionJob.stage == stage)
    if run_id:
        run_job_ids = _repair_job_ids_for_run(db, run_id)
        if not run_job_ids:
            return {"summary": _repair_summary([]), "items": [], "page": page, "page_size": page_size, "total": 0}
        query = query.filter(ProductionJob.id.in_(run_job_ids))
    total = query.count()
    jobs = query.order_by(ProductionJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    plan_ids = list({job.plan_id for job in jobs})
    audit_by_job = _repair_audit_by_job(db, [job.id for job in jobs], plan_ids=plan_ids, run_id=run_id)
    items = [_repair_task_item(job, audit_by_job.get(job.id)) for job in jobs]
    return {"summary": _repair_summary(items), "items": items, "page": page, "page_size": page_size, "total": total}


@router.post("/repair-tasks/{job_id}/retry")
def retry_repair_task(
    job_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    job = _repair_job(db, job_id)
    if job.status not in {JOB_FAILED, JOB_BLOCKED, JOB_RETRY_WAIT}:
        raise HTTPException(status_code=409, detail="当前返修任务状态不允许重试")
    audit = _repair_audit_by_job(db, [job.id], plan_ids=[job.plan_id]).get(job.id) or {}
    repair_task = audit.get("repair_task") or {}
    allowed, reason = _can_retry_repair_job(db, job, repair_task)
    if not allowed:
        raise HTTPException(status_code=409, detail=reason)
    _requeue_repair_job(job)
    db.add(ProductionAuditEvent(
        event_type="agency_repair_retry_requested",
        production_plan_id=job.plan_id,
        payload_json={"job_id": job.id, "stage": job.stage, "target_type": job.target_type, "target_id": job.target_id},
    ))
    db.commit()
    db.refresh(job)
    return _repair_task_item(job, audit)


@router.post("/repair-tasks/{job_id}/authorize-retry")
def authorize_paid_repair_retry(
    job_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    reason = str(body.get("reason") or "").strip()
    confirmed_budget_delta = float(body.get("confirmed_budget_delta") or body.get("budget_delta") or 0.0)
    if not reason:
        raise HTTPException(status_code=422, detail="必须填写继续付费返修原因")
    if confirmed_budget_delta <= 0:
        raise HTTPException(status_code=422, detail="必须确认追加预算金额")
    job = _repair_job(db, job_id)
    if job.status not in {JOB_FAILED, JOB_BLOCKED, JOB_RETRY_WAIT}:
        raise HTTPException(status_code=409, detail="当前返修任务状态不允许授权重试")
    audit = _repair_audit_by_job(db, [job.id], plan_ids=[job.plan_id]).get(job.id) or {}
    repair_task = audit.get("repair_task") or {}
    if not repair_task.get("requires_paid_provider"):
        raise HTTPException(status_code=409, detail="非付费返修请使用普通重试")
    estimated_cost = float(repair_task.get("estimated_cost") or 0.0)
    if confirmed_budget_delta < estimated_cost:
        raise HTTPException(status_code=409, detail="确认追加预算小于预计返修费用")
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == job.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="生产计划不存在")
    run_id = _latest_repair_run_id(db, job.id, job.plan_id)
    policy = _auto_repair_policy_for_run(db, run_id)
    allowed, retry_reason = _can_retry_repair_job(
        db,
        job,
        repair_task,
        policy_override={**policy, "budget_limit": float(policy.get("budget_limit") or 0.0) + confirmed_budget_delta},
    )
    if not allowed:
        raise HTTPException(status_code=409, detail=retry_reason)
    plan.budget_limit = float(plan.budget_limit or 0.0) + confirmed_budget_delta
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first() if run_id else None
    if run:
        trace = dict(run.model_trace_json or {})
        next_policy = dict(trace.get("auto_repair_policy") or {})
        next_policy["budget_limit"] = float(next_policy.get("budget_limit") or 0.0) + confirmed_budget_delta
        trace["auto_repair_policy"] = next_policy
        run.model_trace_json = trace
    if float(plan.current_cost or 0.0) + active_reserved_cost(db, job.plan_id) + estimated_cost > float(plan.budget_limit):
        raise HTTPException(status_code=409, detail="追加预算后生产预算仍不足，需要人工确认")
    _requeue_repair_job(job)
    db.add(ProductionAuditEvent(
        event_type="agency_repair_paid_retry_authorized",
        production_plan_id=job.plan_id,
        payload_json={
            "job_id": job.id,
            "reason": reason,
            "confirmed_budget_delta": confirmed_budget_delta,
            "estimated_cost": estimated_cost,
            "repair_task": repair_task,
        },
    ))
    db.add(ProductionAuditEvent(
        event_type="agency_repair_retry_requested",
        production_plan_id=job.plan_id,
        payload_json={"job_id": job.id, "stage": job.stage, "target_type": job.target_type, "target_id": job.target_id, "authorized": True},
    ))
    db.commit()
    db.refresh(job)
    return _repair_task_item(job, audit)


def _repair_job(db: Session, job_id: str) -> ProductionJob:
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job or not job.stage.startswith("agency_auto_repair"):
        raise HTTPException(status_code=404, detail="返修任务不存在")
    return job


def _requeue_repair_job(job: ProductionJob) -> None:
    job.status = JOB_QUEUED
    job.error_code = None
    job.error_message = None
    job.blocked_reason = None
    job.lease_id = None
    job.leased_until = None


def _repair_audit_by_job(db: Session, job_ids: list[str], *, plan_ids: list[str], run_id: str | None = None) -> dict[str, dict]:
    if not job_ids or not plan_ids:
        return {}
    query = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id.in_(plan_ids))
        .filter(ProductionAuditEvent.event_type.in_(_REPAIR_AUDIT_EVENT_TYPES))
    )
    if run_id:
        query = query.filter(ProductionAuditEvent.run_id == run_id)
    result: dict[str, dict] = {}
    for row in query.order_by(ProductionAuditEvent.created_at.asc()).all():
        payload = row.payload_json or {}
        job_id = payload.get("job_id")
        if job_id not in job_ids:
            continue
        current = result.setdefault(job_id, {})
        if payload.get("repair_task"):
            current["repair_task"] = payload["repair_task"]
        if row.event_type == "agency_repair_recheck_required":
            current["recheck_required"] = True
            current["next_gate"] = (payload.get("result") or {}).get("next_gate")
        current["last_event_type"] = row.event_type
    return result


def _repair_job_ids_for_run(db: Session, run_id: str) -> list[str]:
    rows = (
        db.query(ProductionAuditEvent.payload_json)
        .filter(ProductionAuditEvent.run_id == run_id)
        .filter(ProductionAuditEvent.event_type.in_(_REPAIR_AUDIT_EVENT_TYPES))
        .all()
    )
    job_ids: list[str] = []
    seen = set()
    for (payload,) in rows:
        job_id = (payload or {}).get("job_id")
        if job_id and job_id not in seen:
            seen.add(job_id)
            job_ids.append(job_id)
    return job_ids


def _repair_task_item(job: ProductionJob, audit: dict | None) -> dict:
    repair_task = (audit or {}).get("repair_task") or {}
    return {
        "id": job.id,
        "type": repair_task.get("type") or job.stage.split(":", 1)[-1],
        "stage": repair_task.get("stage") or job.stage,
        "status": job.status,
        "reason": repair_task.get("reason") or job.blocked_reason or "",
        "expected_result": repair_task.get("expected_result") or "",
        "repair_action_label": repair_task.get("repair_action_label") or "联系人工处理",
        "repair_route": repair_task.get("repair_route"),
        "affected_ids": repair_task.get("affected_ids") or [job.target_id],
        "estimated_cost": repair_task.get("estimated_cost") or 0,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "recheck_required": bool((audit or {}).get("recheck_required")) or job.status == "repair_recheck_pending",
        "next_gate": (audit or {}).get("next_gate"),
        "retry_actions": _repair_retry_actions(job, repair_task),
    }


def _repair_retry_actions(job: ProductionJob, repair_task: dict) -> dict:
    repair_type = repair_task.get("type") or job.stage.split(":", 1)[-1]
    requires_paid = bool(repair_task.get("requires_paid_provider"))
    estimated_cost = float(repair_task.get("estimated_cost") or 0.0)
    is_retryable = job.status in {JOB_FAILED, JOB_BLOCKED, JOB_RETRY_WAIT} and repair_type != "manual_incomplete_repair_task"
    return {
        "normal_retry_enabled": is_retryable and not requires_paid,
        "retry_enabled": is_retryable and not requires_paid,
        "paid_authorize_required": is_retryable and requires_paid,
        "paid_authorization_required": is_retryable and requires_paid,
        "manual_action_enabled": bool(repair_task.get("repair_route")),
        "primary_label": "确认追加预算并重试" if is_retryable and requires_paid else ("重试返修" if is_retryable else (repair_task.get("repair_action_label") if repair_task.get("repair_route") else "去处理")),
        "reason": "需要人工确认追加预算后才能继续付费返修" if is_retryable and requires_paid else "",
        "estimated_cost": estimated_cost,
        "budget_gap": max(estimated_cost, 0.0),
    }


def _repair_summary(items: list[dict]) -> dict:
    summary = {"total": len(items), "queued": 0, "running": 0, "completed": 0, "failed": 0, "manual_required": 0, "recheck_required": 0}
    for item in items:
        status = item["status"]
        if status in summary:
            summary[status] += 1
        if item.get("recheck_required"):
            summary["recheck_required"] += 1
        if status in {JOB_FAILED, JOB_BLOCKED}:
            summary["manual_required"] += 1
    summary["active"] = summary["queued"] + summary["running"]
    return summary


def _can_retry_repair_job(
    db: Session,
    job: ProductionJob,
    repair_task: dict,
    *,
    policy_override: dict | None = None,
) -> tuple[bool, str]:
    if not repair_task:
        return False, "缺少原始返修任务信息，需要人工确认"
    run_id = _latest_repair_run_id(db, job.id, job.plan_id)
    policy = policy_override or _auto_repair_policy_for_run(db, run_id)
    if not policy.get("enabled"):
        return False, "自动返修策略未启用，需要人工确认"
    if repair_task.get("stage") not in set(policy.get("allowed_stages") or []):
        return False, "当前阶段未授权自动返修"
    if repair_task.get("type") not in set(policy.get("allowed_types") or []):
        return False, "当前返修类型未授权自动执行"
    next_round = _next_retry_round_for_job(db, job, repair_task, run_id)
    if next_round > int(policy.get("max_rounds") or 0):
        return False, "自动返修轮数已达上限"
    if not repair_task.get("requires_paid_provider"):
        return True, ""
    estimated_cost = float(repair_task.get("estimated_cost") or 0.0)
    if _repair_budget_used_for_plan(db, job.plan_id, run_id) + estimated_cost > float(policy.get("budget_limit") or 0.0):
        return False, "自动返修预算不足，需要人工确认是否继续付费返修"
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == job.plan_id).first()
    if not plan or plan.budget_limit is None:
        return False, "生产预算未配置，需要人工确认"
    if float(plan.current_cost or 0.0) + active_reserved_cost(db, job.plan_id) + estimated_cost > float(plan.budget_limit):
        return False, "生产预算不足，需要人工确认是否继续付费返修"
    return True, ""


def _next_retry_round_for_job(db: Session, job: ProductionJob, repair_task: dict, run_id: str | None) -> int:
    created_rounds = 0
    creation_query = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id == job.plan_id)
        .filter(ProductionAuditEvent.event_type == "agency_repair_task_created")
    )
    if run_id:
        creation_query = creation_query.filter(ProductionAuditEvent.run_id == run_id)
    for event in creation_query.all():
        payload = event.payload_json or {}
        candidate = payload.get("repair_task") or {}
        if _repair_task_scope(candidate, fallback_job=job) == _repair_task_scope(repair_task, fallback_job=job):
            created_rounds += 1

    retry_count = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id == job.plan_id)
        .filter(ProductionAuditEvent.event_type == "agency_repair_retry_requested")
        .filter(ProductionAuditEvent.payload_json["job_id"].as_string() == job.id)
        .count()
    )
    return max(1, created_rounds) + retry_count + 1


def _repair_task_scope(repair_task: dict, *, fallback_job: ProductionJob) -> tuple[str, str, str, str]:
    repair_type = str(repair_task.get("type") or fallback_job.stage.split(":", 1)[-1])
    stage = str(repair_task.get("stage") or fallback_job.stage)
    target_type = str(repair_task.get("target_type") or fallback_job.target_type)
    target_id = str(repair_task.get("target_id") or fallback_job.target_id)
    return stage, repair_type, target_type, target_id


def _latest_repair_run_id(db: Session, job_id: str, plan_id: str) -> str | None:
    rows = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id == plan_id)
        .filter(ProductionAuditEvent.event_type == "agency_repair_task_created")
        .order_by(ProductionAuditEvent.created_at.desc())
        .all()
    )
    for event in rows:
        if (event.payload_json or {}).get("job_id") == job_id:
            return event.run_id
    return None


def _auto_repair_policy_for_run(db: Session, run_id: str | None) -> dict:
    if not run_id:
        return {}
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    return ((run.model_trace_json or {}).get("auto_repair_policy") or {}) if run else {}


def _repair_budget_used_for_plan(db: Session, plan_id: str, run_id: str | None) -> float:
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
