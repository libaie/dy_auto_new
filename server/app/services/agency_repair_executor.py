from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import Character, ProductionAuditEvent, ProductionJob, Scene
from app.services.agency_repair_contracts import AUTO_REPAIR_STAGE
from app.services.production_action_result import ProductionActionResult


async def execute_repair_job(db: Session, job: ProductionJob) -> ProductionActionResult:
    repair_type = job.stage.split(":", 1)[1] if ":" in job.stage else ""
    if repair_type == "storyboard_missing_references":
        return _mark_recheck_required(db, job, "已记录分镜参考缺口，等待复审确认")
    if repair_type == "missing_character_reference":
        return await _manual_paid_reference_block(db, job, "去角色资产补参考图", f"/characters/{job.target_id}")
    if repair_type == "missing_scene_reference":
        return await _manual_paid_reference_block(db, job, "去场景资产补参考图", f"/scenes/{job.target_id}")
    if repair_type in {"image_generation_failed", "image_generation_timeout", "video_segment_failed", "video_segment_timeout"}:
        return _mark_recheck_required(db, job, "已记录阶段返修请求，等待重新审查")
    return ProductionActionResult.blocked(
        "AGENCY_REPAIR_MANUAL_REQUIRED",
        "自动返修类型暂不支持，需要人工确认",
        "去审查中心处理",
        repair_route="/ai-video-review",
        affected_ids=[job.id],
        retryable=False,
    )


async def _manual_paid_reference_block(
    db: Session,
    job: ProductionJob,
    action_label: str,
    route: str,
) -> ProductionActionResult:
    # Reference generation may call paid providers and existing helpers commit internally.
    # Keep this path manual until a caller-owned cost reservation path is available.
    db.add(ProductionAuditEvent(
        event_type="agency_repair_manual_required",
        production_plan_id=job.plan_id,
        payload_json={
            "job_id": job.id,
            "reason": "参考图返修需要付费模型和成本预留路径，需要人工确认",
            "repair_action_label": action_label,
            "repair_route": route,
        },
    ))
    return ProductionActionResult.blocked(
        "AGENCY_REPAIR_MANUAL_REQUIRED",
        "参考图返修需要人工确认付费路径",
        action_label,
        repair_route=route,
        affected_ids=[job.target_id],
        retryable=False,
    )


def _mark_recheck_required(db: Session, job: ProductionJob, message: str) -> ProductionActionResult:
    _mark_target_recheck_pending(db, job)
    db.add(ProductionAuditEvent(
        event_type="agency_repair_recheck_required",
        production_plan_id=job.plan_id,
        payload_json={
            "job_id": job.id,
            "result": {"next_gate": _next_gate_for_job(job)},
            "message": message,
        },
    ))
    db.flush()
    return ProductionActionResult.success(
        message,
        {
            "job_id": job.id,
            "next_gate": _next_gate_for_job(job),
            "repair_recheck_pending": True,
        },
    )


def _mark_target_recheck_pending(db: Session, job: ProductionJob) -> None:
    if job.target_type == "character":
        row = db.query(Character).filter(Character.id == job.target_id).first()
    elif job.target_type == "scene":
        row = db.query(Scene).filter(Scene.id == job.target_id).first()
    else:
        row = None
    if not row:
        return
    meta = dict(row.meta_json or {})
    meta["repair_recheck_pending"] = True
    meta["repair_recheck_job_id"] = job.id
    meta["repair_recheck_at"] = bj_now().isoformat()
    row.meta_json = meta


def _next_gate_for_job(job: ProductionJob) -> str:
    if job.target_type == "character":
        return "角色资产审查"
    if job.target_type == "scene":
        return "场景资产审查"
    if "image" in job.stage:
        return "图像审查"
    if "video" in job.stage:
        return "视频审查"
    return "人工审查"


def is_agency_repair_stage(stage: str) -> bool:
    return stage.startswith(f"{AUTO_REPAIR_STAGE}:") or stage == AUTO_REPAIR_STAGE
