"""Staged video production orchestration owned by dy_auto."""
import logging

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import (
    Episode,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
from app.services.audit_gate import classify_audit_gate
from app.services.pixelle_stage_client import get_stage_task, submit_image_batch
from app.services.runtime_model_config import redact_runtime_model_config, resolve_runtime_model_config

logger = logging.getLogger(__name__)


class VideoProductionError(ValueError):
    pass


def _frame_id(frame: dict, index: int) -> str:
    return str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}")


def create_run_from_episode(db: Session, series_id: str, episode_id: str) -> VideoProductionRun:
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise VideoProductionError("Episode not found")
    storyboard = episode.storyboard_json or {}
    frames = storyboard.get("frames") or []
    if not frames:
        raise VideoProductionError("Episode storyboard_json is empty")

    normalized_frames = []
    for index, frame in enumerate(frames):
        normalized_frames.append({**frame, "frame_id": _frame_id(frame, index)})

    run = VideoProductionRun(
        series_id=series_id,
        episode_id=episode_id,
        status="draft",
        current_stage="storyboard_ready",
        storyboard_json={**storyboard, "frames": normalized_frames},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def image_stage_frames(run: VideoProductionRun) -> list[dict]:
    frames = (run.storyboard_json or {}).get("frames") or []
    return [{
        "frame_id": _frame_id(frame, index),
        "image_prompt": frame.get("image_prompt", ""),
        "reference_urls": frame.get("reference_urls") or [],
        "style_constraints": {
            "character_ids": frame.get("character_ids") or [],
            "scene_id": frame.get("scene_id"),
            "continuity_notes": frame.get("continuity_notes", ""),
        },
        "duration": float(frame.get("duration") or 5),
    } for index, frame in enumerate(frames)]


def mark_image_stage_submitted(db: Session, run: VideoProductionRun, stage_task_id: str, model_trace: dict) -> VideoProductionRun:
    run.status = "image_batch_running"
    run.current_stage = "image_generation"
    run.pixelle_stage_task_id = stage_task_id
    run.model_trace_json = model_trace
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run


def _next_asset_version(db: Session, run_id: str, frame_id: str, asset_type: str) -> int:
    latest = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.frame_id == frame_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.version.desc()).first()
    return (latest.version + 1) if latest else 1


def mark_image_stage_assets(db: Session, run: VideoProductionRun, assets: list[dict], pixelle_task_id: str) -> list[VideoProductionAsset]:
    saved = []
    for item in assets:
        frame_id = item["frame_id"]
        asset = VideoProductionAsset(
            run_id=run.id,
            episode_id=run.episode_id,
            frame_id=frame_id,
            asset_type="image",
            stage="image_generation",
            url=item.get("url", ""),
            local_path=item.get("local_path", ""),
            thumbnail_url=item.get("thumbnail_url", ""),
            version=_next_asset_version(db, run.id, frame_id, "image"),
            metadata_json=item.get("metadata", {}),
            status="review_pending",
            pixelle_task_id=pixelle_task_id,
        )
        db.add(asset)
        saved.append(asset)
    run.status = "image_review_pending"
    run.current_stage = "image_review"
    run.updated_at = bj_now()
    db.commit()
    for asset in saved:
        db.refresh(asset)
    return saved


def run_ai_audit_for_assets(db: Session, run: VideoProductionRun, assets: list[VideoProductionAsset]) -> list[VideoProductionAsset]:
    """Run AI audit on each asset and create review records. Assets that pass gate become approved."""
    try:
        from app.services.model_registry import get_model_for_scene, ModelResolutionError
        audit_model = get_model_for_scene(db, "quality_audit")
    except Exception:
        audit_model = {}

    for asset in assets:
        if not asset.url:
            _record_audit_fallback(db, asset, run.id, ["No asset URL for audit"])
            continue

        if not audit_model or not audit_model.get("api_key"):
            _record_audit_fallback(db, asset, run.id, ["Audit model not configured or missing API key"])
            continue

        try:
            from app.routers.audit import _do_audit
            result = _do_audit(audit_model, asset.url, None)
        except Exception as exc:
            logger.warning("AI audit failed for asset %s: %s", asset.id, exc)
            result = {"score": 0.0, "pass_fail": False, "issues": [str(exc)], "raw": ""}

        gate = classify_audit_gate(result, error=False)
        db.add(VideoReviewRecord(
            asset_id=asset.id,
            run_id=run.id,
            review_type="ai",
            status=gate["gate_status"],
            score=gate["score"],
            issues_json=gate.get("issues", []),
            model_trace_json={"auditor_model": audit_model.get("provider", "unknown"), "auditor_model_name": audit_model.get("model_name", "")},
        ))

        if gate["gate_status"] == "approved":
            asset.status = "approved"
        else:
            asset.status = "review_pending"

    db.commit()
    for asset in assets:
        db.refresh(asset)
    return assets


def _record_audit_fallback(db: Session, asset: VideoProductionAsset, run_id: str, issues: list[str]) -> None:
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=run_id,
        review_type="ai",
        status="needs_human",
        score=0.0,
        issues_json=issues,
        model_trace_json={},
    ))


def reject_asset(db: Session, asset_id: str, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")
    latest = latest_assets_by_frame(db, asset.run_id, asset.asset_type).get(asset.frame_id)
    if latest and latest.id != asset.id:
        raise VideoProductionError("A newer asset version exists. Reload before reviewing.")
    asset.status = "rejected"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="rejected",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
    ))
    db.commit()
    db.refresh(asset)
    return asset


def latest_assets_by_frame(db: Session, run_id: str, asset_type: str = "image") -> dict[str, VideoProductionAsset]:
    rows = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.frame_id.asc(), VideoProductionAsset.version.desc()).all()
    latest = {}
    for row in rows:
        latest.setdefault(row.frame_id, row)
    return latest


def latest_approved_assets_by_frame(db: Session, run_id: str, asset_type: str = "image") -> dict[str, VideoProductionAsset]:
    latest = latest_assets_by_frame(db, run_id, asset_type)
    return {frame_id: asset for frame_id, asset in latest.items() if asset.status == "approved"}


def approve_asset(db: Session, asset_id: str, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")
    latest = latest_assets_by_frame(db, asset.run_id, asset.asset_type).get(asset.frame_id)
    if latest and latest.id != asset.id:
        raise VideoProductionError("A newer asset version exists. Reload before reviewing.")
    asset.status = "approved"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="approved",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
    ))
    db.commit()
    db.refresh(asset)
    return asset


async def start_image_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    frames = image_stage_frames(run)
    if not frames:
        raise VideoProductionError("Run has no storyboard frames")
    model_config = resolve_runtime_model_config(db, "image_generation")
    response = await submit_image_batch(
        db=db,
        run_id=run.id,
        episode_id=run.episode_id,
        frames=frames,
        model_config=model_config,
    )
    return mark_image_stage_submitted(
        db,
        run,
        response["stage_task_id"],
        {"image_generation": redact_runtime_model_config(model_config)},
    )


async def sync_image_stage_results(db: Session, run_id: str) -> list[VideoProductionAsset]:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Image stage is not complete: {status.get('status')}")
    assets = mark_image_stage_assets(db, run, status.get("assets", []), pixelle_task_id=run.pixelle_stage_task_id)
    run_ai_audit_for_assets(db, run, assets)
    return assets


def create_regenerated_image_asset(db: Session, asset_id: str, generated: dict) -> VideoProductionAsset:
    old = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not old:
        raise VideoProductionError("Asset not found")
    old.status = "regenerating"
    new_asset = VideoProductionAsset(
        run_id=old.run_id,
        episode_id=old.episode_id,
        frame_id=old.frame_id,
        asset_type="image",
        stage="image_generation",
        url=generated.get("url", ""),
        local_path=generated.get("local_path", ""),
        thumbnail_url=generated.get("thumbnail_url", ""),
        version=_next_asset_version(db, old.run_id, old.frame_id, "image"),
        metadata_json=generated.get("metadata", {}),
        status="review_pending",
        pixelle_task_id=generated.get("pixelle_task_id"),
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    return new_asset
