from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProductionAuditEvent, ProductionJob, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.domains.video_production.production_queue_service import enqueue_job


AUTO_REPAIR_STAGE = "agency_auto_repair"
BACKTRACK_FAILURE_THRESHOLD = 3
BACKTRACK_FAILURE_STATUSES = {"rejected", "failed", "blocked", "needs_human"}


def trigger_backtrack_if_needed(
    db: Session,
    run: VideoProductionRun,
    asset: VideoProductionAsset,
    *,
    reason: str,
) -> dict[str, Any]:
    if not run.production_plan_id:
        return {"triggered": False, "reason": "missing_production_plan"}
    if asset.asset_type not in {"image", "video_segment"}:
        return {"triggered": False, "reason": "unsupported_asset_type"}

    failure_count = _failure_count(db, run, asset)
    if failure_count < BACKTRACK_FAILURE_THRESHOLD:
        return {"triggered": False, "failure_count": failure_count}

    target_type, target_id = _target_scope(asset)
    repair_type, backtrack_to = _repair_for_asset(asset)
    key_prefix = f"backtrack:{run.id}:{run.production_plan_id}:{repair_type}:{target_type}:{target_id}:asset-v{asset.version}:"
    existing = (
        db.query(ProductionJob)
        .filter(ProductionJob.idempotency_key.like(f"{key_prefix}%"))
        .order_by(ProductionJob.created_at.desc())
        .first()
    )
    if existing:
        _apply_backtrack_run_state(run, backtrack_to)
        db.flush()
        db.refresh(run)
        return {
            "triggered": True,
            "deduped": True,
            "failure_count": failure_count,
            "job_id": existing.id,
            "backtrack_to": backtrack_to,
        }

    idempotency_key = f"{key_prefix}cycle-1"
    job = enqueue_job(
        db,
        run.production_plan_id,
        target_type,
        target_id,
        f"{AUTO_REPAIR_STAGE}:{repair_type}",
        idempotency_key,
        priority=5,
        max_attempts=2,
        commit=False,
    )
    job.blocked_reason = reason[:120]
    db.add(ProductionAuditEvent(
        event_type="agency_backtrack_triggered",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        production_segment_id=asset.production_segment_id,
        payload_json={
            "asset_id": asset.id,
            "asset_type": asset.asset_type,
            "target_type": target_type,
            "target_id": target_id,
            "failure_count": failure_count,
            "threshold": BACKTRACK_FAILURE_THRESHOLD,
            "repair_type": repair_type,
            "backtrack_to": backtrack_to,
            "reason": reason,
            "job_id": job.id,
        },
    ))
    _apply_backtrack_run_state(run, backtrack_to)
    run.updated_at = bj_now()
    db.flush()
    db.refresh(job)
    db.refresh(run)
    return {
        "triggered": True,
        "deduped": False,
        "failure_count": failure_count,
        "job_id": job.id,
        "backtrack_to": backtrack_to,
    }


def _failure_count(db: Session, run: VideoProductionRun, asset: VideoProductionAsset) -> int:
    query = (
        db.query(VideoReviewRecord)
        .join(VideoProductionAsset, VideoReviewRecord.asset_id == VideoProductionAsset.id)
        .filter(VideoReviewRecord.run_id == run.id)
        .filter(VideoProductionAsset.asset_type == asset.asset_type)
        .filter(VideoReviewRecord.status.in_(BACKTRACK_FAILURE_STATUSES))
        .filter(VideoReviewRecord.is_latest_asset_review.is_(True))
    )
    if asset.target_type and asset.target_id:
        query = query.filter(VideoReviewRecord.target_type == asset.target_type, VideoReviewRecord.target_id == asset.target_id)
    elif asset.production_segment_id:
        query = query.filter(VideoReviewRecord.production_segment_id == asset.production_segment_id)
    else:
        query = query.filter(VideoReviewRecord.asset_id == asset.id)
    attempts = set()
    for review in query.all():
        attempts.add((review.asset_id, int(review.asset_version or 0)))
    return len(attempts)


def _target_scope(asset: VideoProductionAsset) -> tuple[str, str]:
    target_type = asset.target_type or ("production_segment" if asset.production_segment_id else "asset")
    target_id = asset.target_id or asset.production_segment_id or asset.id
    return target_type, target_id


def _repair_for_asset(asset: VideoProductionAsset) -> tuple[str, str]:
    if asset.asset_type == "video_segment":
        return "video_segment_failed", "image_generation"
    return "image_generation_failed", "storyboard"


def _apply_backtrack_run_state(run: VideoProductionRun, backtrack_to: str) -> None:
    run.current_stage = backtrack_to
    if backtrack_to == "image_generation":
        run.status = "image_batch_running"
    elif backtrack_to == "storyboard":
        run.status = "image_human_review_required"
    run.updated_at = bj_now()
