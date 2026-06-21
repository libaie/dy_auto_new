"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 video_production_readiness 相关业务规则、状态转换和外部系统边界。
"""

from sqlalchemy.orm import Session

from app.db.models.video_production import ProductionJob
from app.domains.video_production.production_status import JOB_BLOCKED

from app.domains.video_production.video_production_run_types import get_run_type
from app.domains.video_production.video_production_state import (
    IMAGE_READY_STATUS,
    VIDEO_READY_STATUS,
    latest_assets_by_frame,
    production_segment_frame_ids,
)


REVIEW_ROUTE = "/ai-video-review?run_id={run_id}"
PRODUCTION_ROUTE = "/video-production/{run_id}"


def _empty_counts() -> dict:
    return {"total": 0, "approved": 0, "pending": 0, "failed": 0}


def _latest_assets(db: Session, run_id: str) -> dict:
    return {
        asset_type: latest_assets_by_frame(db, run_id, asset_type)
        for asset_type in ("image", "video_segment", "final_video")
    }


def _asset_counts(latest_assets: dict) -> dict:
    counts = {
        "image": _empty_counts(),
        "video_segment": _empty_counts(),
        "final_video": _empty_counts(),
    }
    for asset_type, assets_by_frame in latest_assets.items():
        bucket = counts[asset_type]
        for asset in assets_by_frame.values():
            bucket["total"] += 1
            if asset.status == "approved":
                bucket["approved"] += 1
            elif asset.status in {"failed", "rejected"}:
                bucket["failed"] += 1
            else:
                bucket["pending"] += 1
    return counts


def _has_blocking_assets(counts: dict, asset_type: str) -> bool:
    return counts[asset_type]["pending"] > 0 or counts[asset_type]["failed"] > 0


def _missing_or_unapproved_expected_frames(expected_frame_ids: list[str], assets_by_frame: dict) -> list[str]:
    return [
        frame_id
        for frame_id in expected_frame_ids
        if not assets_by_frame.get(frame_id) or assets_by_frame[frame_id].status != "approved"
    ]


def _review_block(code: str, message: str, repair_action: str, run_id: str) -> dict:
    return {
        "code": code,
        "message": message,
        "repair_action": repair_action,
        "repair_route": REVIEW_ROUTE.format(run_id=run_id),
        "retryable": False,
        "affected_ids": [run_id],
    }


def _production_block(code: str, message: str, repair_action: str, run_id: str) -> dict:
    return {
        "code": code,
        "message": message,
        "repair_action": repair_action,
        "repair_route": PRODUCTION_ROUTE.format(run_id=run_id),
        "retryable": False,
        "affected_ids": [run_id],
    }


def _next_action(key: str, label: str) -> dict:
    return {"key": key, "label": label}


def _video_gate_relevant(status: str) -> bool:
    return status not in {
        "draft",
        "storyboard_ready",
        "image_batch_running",
        "image_review_pending",
        "image_human_review_required",
        IMAGE_READY_STATUS,
    }


def _image_gate_relevant(status: str) -> bool:
    return status not in {
        "draft",
        "storyboard_ready",
        "reference_generation_running",
        "reference_generation_blocked",
        "image_batch_running",
    }


def _blocked_compose_jobs(db: Session, run) -> list[ProductionJob]:
    if not run.production_plan_id:
        return []
    return (
        db.query(ProductionJob)
        .filter(ProductionJob.plan_id == run.production_plan_id)
        .filter(ProductionJob.stage.in_(["episode_compose", "composition"]))
        .filter(ProductionJob.status == JOB_BLOCKED)
        .order_by(ProductionJob.created_at.desc())
        .all()
    )


def build_run_readiness(db: Session, run) -> dict:
    run_type = get_run_type(run)
    if run.status in {"reference_generation_running", "reference_generation_blocked"}:
        return {
            "run_id": run.id,
            "run_type": run_type,
            "status": run.status,
            "current_stage": run.current_stage,
            "can_start_images": False,
            "can_start_videos": False,
            "can_compose": False,
            "can_complete_final": False,
            "needs_review": False,
            "next_action": _next_action(
                "wait_reference_generation" if run.status == "reference_generation_running" else "repair_reference_generation",
                "等待参考图生成" if run.status == "reference_generation_running" else "修复参考图生成",
            ),
            "blocks": [],
            "asset_counts": {
                "image": _empty_counts(),
                "video_segment": _empty_counts(),
                "final_video": _empty_counts(),
            },
        }
    latest_assets = _latest_assets(db, run.id)
    counts = _asset_counts(latest_assets)
    expected_frame_ids = production_segment_frame_ids(db, run)
    blocks = []
    next_action = None

    missing_or_unapproved_images = _missing_or_unapproved_expected_frames(
        expected_frame_ids,
        latest_assets["image"],
    )
    missing_or_unapproved_videos = _missing_or_unapproved_expected_frames(
        expected_frame_ids,
        latest_assets["video_segment"],
    )
    image_blocked = _image_gate_relevant(run.status) and bool(missing_or_unapproved_images)
    video_blocked = _video_gate_relevant(run.status) and bool(missing_or_unapproved_videos)
    final_blocked = _has_blocking_assets(counts, "final_video")
    blocked_compose_jobs = _blocked_compose_jobs(db, run)
    compose_preflight_blocked = (
        run.status == "final_review_pending"
        and counts["final_video"]["total"] == 0
        and bool(blocked_compose_jobs)
    )

    can_start_images = run.status in {"draft", "storyboard_ready"}
    can_start_videos = run.status == IMAGE_READY_STATUS and not image_blocked
    can_compose = run.status == VIDEO_READY_STATUS and not video_blocked
    can_complete_final = (
        run.status == "final_review_pending"
        and not image_blocked
        and not video_blocked
        and not final_blocked
        and not compose_preflight_blocked
    )

    if image_blocked:
        can_start_videos = False
        can_compose = False
        can_complete_final = False
        blocks.append(_review_block(
            "IMAGE_REVIEW_REQUIRED",
            "启动视频生成前必须完成人工图像审查。",
            "打开审查中心，逐个通过或驳回待审图像。",
            run.id,
        ))
    if video_blocked:
        can_compose = False
        can_complete_final = False
        blocks.append(_review_block(
            "VIDEO_REVIEW_REQUIRED",
            "最终合成前必须完成人工视频片段审查。",
            "打开审查中心，逐个通过或驳回待审视频片段。",
            run.id,
        ))
    if final_blocked:
        can_complete_final = False
        blocks.append(_review_block(
            "FINAL_REVIEW_REQUIRED",
            "入库前必须完成最终成片人工审查。",
            "打开审查中心，确认最终成片后再入库。",
            run.id,
        ))
    if compose_preflight_blocked:
        can_complete_final = False
        job = blocked_compose_jobs[0]
        blocks.append(_production_block(
            job.error_code or "COMPOSE_PREFLIGHT_BLOCKED",
            job.error_message or "最终合成预检被专家团队阻断，需要先处理生产任务。",
            "返回生产监控台，查看被阻断的合成任务和专家修复建议。",
            run.id,
        ))

    if run.status == "reference_generation_running":
        next_action = _next_action("wait_reference_generation", "等待参考图生成")
    elif run.status == "reference_generation_blocked":
        next_action = _next_action("repair_reference_generation", "修复参考图生成")
    elif compose_preflight_blocked:
        next_action = _next_action("repair_provider_stage", "修复生产任务")
    elif blocks:
        next_action = _next_action("open_review", "\u6253\u5f00\u5ba1\u67e5")
    elif run.status in {"draft", "storyboard_ready"}:
        next_action = _next_action("start_images", "\u5f00\u59cb\u751f\u6210\u56fe\u7247")
    elif run.status == IMAGE_READY_STATUS:
        next_action = _next_action("start_videos", "\u5f00\u59cb\u751f\u6210\u89c6\u9891")
    elif run.status == VIDEO_READY_STATUS:
        next_action = _next_action("compose", "\u5408\u6210\u7ec8\u7247")
    elif run.status == "final_review_pending":
        next_action = _next_action("open_review", "\u6253\u5f00\u5ba1\u67e5")
    elif run.status in {"image_batch_running", "video_batch_running", "composing", "running"}:
        next_action = _next_action("sync_provider", "\u540c\u6b65\u4f9b\u5e94\u5546")
    elif run.status == "completed":
        next_action = _next_action("completed", "\u5df2\u5b8c\u6210")

    return {
        "run_id": run.id,
        "run_type": run_type,
        "status": run.status,
        "current_stage": run.current_stage,
        "can_start_images": can_start_images,
        "can_start_videos": can_start_videos,
        "can_compose": can_compose,
        "can_complete_final": can_complete_final,
        "needs_review": bool(blocks),
        "next_action": next_action,
        "blocks": blocks,
        "asset_counts": counts,
    }
