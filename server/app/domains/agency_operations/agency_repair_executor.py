"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_repair_executor 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models import (
    Character,
    ProductionAuditEvent,
    ProductionJob,
    ProductionSegment,
    Scene,
    VideoProductionRun,
)
from app.domains.agency_operations.agency_repair_contracts import AUTO_REPAIR_STAGE
from app.domains.video_production.production_action_result import ProductionActionResult
from app.domains.video_production.production_queue_service import enqueue_job
from app.domains.video_production.production_status import (
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
    JOB_RUNNING,
    SEGMENT_IMAGE_QUEUED,
)


ACTIVE_DOWNSTREAM_JOB_STATUSES = {JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT}


async def execute_repair_job(db: Session, job: ProductionJob) -> ProductionActionResult:
    repair_type = job.stage.split(":", 1)[1] if ":" in job.stage else ""
    if repair_type == "storyboard_missing_references":
        if job.target_type == "production_segment":
            return _micro_tune_segment_prompt(db, job, repair_type)
        return _mark_recheck_required(db, job, "已记录分镜参考缺口，等待复审确认")
    if repair_type == "missing_character_reference":
        return await _manual_paid_reference_block(db, job, "去角色资产补参考图", f"/characters/{job.target_id}")
    if repair_type == "missing_scene_reference":
        return await _manual_paid_reference_block(db, job, "去场景资产补参考图", f"/scenes/{job.target_id}")
    if repair_type in {"image_generation_failed", "image_generation_timeout", "video_segment_failed", "video_segment_timeout"}:
        if job.target_type == "production_segment":
            return _micro_tune_segment_prompt(db, job, repair_type)
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


def _micro_tune_segment_prompt(db: Session, job: ProductionJob, repair_type: str) -> ProductionActionResult:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == job.target_id).first()
    if not segment:
        return _mark_recheck_required(db, job, "已记录阶段返修请求，等待重新审查")
    if repair_type == "storyboard_missing_references" and not _segment_has_reference_payload(segment):
        return _block_missing_segment_references(db, job, segment)

    before = {
        "image_prompt": segment.image_prompt,
        "video_prompt": segment.video_prompt,
        "status": segment.status,
        "retry_count": segment.retry_count,
    }
    run = _run_for_repair_job(db, job)
    downstream_key = _downstream_image_job_key(job, segment.id, run)
    downstream_job = db.query(ProductionJob).filter(ProductionJob.idempotency_key == downstream_key).first()
    first_dispatch = downstream_job is None
    suffix = _prompt_tune_suffix(repair_type)

    if first_dispatch:
        if suffix not in segment.image_prompt:
            segment.image_prompt = f"{segment.image_prompt}\n{suffix}".strip()
        if repair_type.startswith("video") and suffix not in segment.video_prompt:
            segment.video_prompt = f"{segment.video_prompt}\n{suffix}".strip()
        segment.retry_count = int(segment.retry_count or 0) + 1
        segment.status = SEGMENT_IMAGE_QUEUED
    if run and (first_dispatch or downstream_job.status in ACTIVE_DOWNSTREAM_JOB_STATUSES):
        run.status = "image_batch_running"
        run.current_stage = "image_generation"
        run.updated_at = bj_now()
    if first_dispatch:
        # 这里把后续生产或返修动作放入统一队列，保证租约、重试和审计边界一致。
        downstream_job = enqueue_job(
            db,
            job.plan_id,
            "production_segment",
            segment.id,
            "image_generation",
            downstream_key,
            priority=max(1, int(job.priority or 100) - 1),
            commit=False,
        )
        db.add(ProductionAuditEvent(
            event_type="agency_repair_prompt_tuned",
            production_plan_id=job.plan_id,
            production_segment_id=segment.id,
            payload_json={
                "job_id": job.id,
                "repair_type": repair_type,
                "target_type": job.target_type,
                "target_id": job.target_id,
                "before": before,
                "after": {
                    "image_prompt": segment.image_prompt,
                    "video_prompt": segment.video_prompt,
                    "status": segment.status,
                    "retry_count": segment.retry_count,
                },
                "downstream_job_id": downstream_job.id,
                "downstream_stage": downstream_job.stage,
                "next_gate": "图像审查",
            },
        ))
        db.add(ProductionAuditEvent(
            event_type="agency_repair_recheck_required",
            production_plan_id=job.plan_id,
            production_segment_id=segment.id,
            payload_json={
                "job_id": job.id,
                "result": {"next_gate": "图像审查"},
                "message": "已自动微调提示词并回退到图像生成，等待复审确认",
            },
        ))
    db.flush()
    return ProductionActionResult.success(
        "已自动微调提示词并回退到图像生成",
        {
            "job_id": job.id,
            "next_gate": "图像审查",
            "repair_recheck_pending": True,
            "prompt_tuned": first_dispatch,
            "downstream_job_id": downstream_job.id,
        },
    )


def _run_for_repair_job(db: Session, job: ProductionJob) -> VideoProductionRun | None:
    run_id = _run_id_from_repair_event(db, job)
    if run_id:
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
        if run:
            return run
    return (
        db.query(VideoProductionRun)
        .filter(VideoProductionRun.production_plan_id == job.plan_id)
        .order_by(VideoProductionRun.created_at.desc())
        .first()
    )


def _run_id_from_repair_event(db: Session, job: ProductionJob) -> str | None:
    events = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id == job.plan_id)
        .filter(ProductionAuditEvent.run_id.isnot(None))
        .order_by(ProductionAuditEvent.created_at.desc())
        .all()
    )
    for event in events:
        payload = event.payload_json or {}
        if payload.get("job_id") == job.id:
            return event.run_id
        job_ids = payload.get("job_ids")
        if isinstance(job_ids, list) and job.id in job_ids:
            return event.run_id
    return None


def _downstream_image_job_key(job: ProductionJob, segment_id: str, run: VideoProductionRun | None) -> str:
    owner_id = run.id if run else job.plan_id
    return f"{owner_id}:{segment_id}:agency_repair:{job.id}:image_generation"


def _segment_has_reference_payload(segment: ProductionSegment) -> bool:
    for item in segment.reference_roles_json or []:
        if isinstance(item, dict) and str(item.get("url") or "").strip():
            return True
    return False


def _block_missing_segment_references(
    db: Session,
    job: ProductionJob,
    segment: ProductionSegment,
) -> ProductionActionResult:
    run = _run_for_repair_job(db, job)
    repair_route = f"/video-production/{run.id}" if run else "/video-production"
    db.add(ProductionAuditEvent(
        event_type="agency_repair_manual_required",
        production_plan_id=job.plan_id,
        production_segment_id=segment.id,
        payload_json={
            "job_id": job.id,
            "reason": "片段缺少角色/场景参考图，自动提示词微调无法补齐真实参考素材",
            "repair_action_label": "去生产监控补齐参考图",
            "repair_route": repair_route,
        },
    ))
    db.flush()
    return ProductionActionResult.blocked(
        "AGENCY_REPAIR_MANUAL_REQUIRED",
        "片段缺少角色/场景参考图，需要先补齐参考素材",
        "去生产监控补齐参考图",
        repair_route=repair_route,
        affected_ids=[segment.id],
        retryable=False,
    )


def _prompt_tune_suffix(repair_type: str) -> str:
    if repair_type.startswith("video"):
        return "自动返修提示：上一轮视频审核未通过，先回退重做关键帧图像；保持角色、服装、场景和光线一致，修复主体畸变、跳帧、运动不连贯和画面崩坏。"
    if repair_type.startswith("storyboard"):
        return "自动返修提示：补充分镜参考和画面约束；强化主体、场景、动作、镜头景别和连续性，避免文字、水印和无关物体。"
    return "自动返修提示：上一轮图像审核未通过，进行局部重绘式修正；保持主体一致，修复面部、手部、构图、光线和背景瑕疵，避免文字、水印和畸形。"


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
