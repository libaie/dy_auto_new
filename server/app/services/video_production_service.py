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
from app.services.pixelle_stage_client import (
    get_stage_task,
    submit_compose,
    submit_image_batch,
    submit_video_batch,
)
from app.services.runtime_model_config import redact_runtime_model_config, resolve_runtime_model_config
from app.services.video_production_state import (
    assert_can_compose,
    assert_can_start_images,
    assert_can_start_videos,
    latest_assets_by_frame,
    record_stage_task,
    recompute_run_gate,
)

logger = logging.getLogger(__name__)


class VideoProductionError(ValueError):
    pass


def _frame_id(frame: dict, index: int) -> str:
    return str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}")


def _next_asset_version(db: Session, run_id: str, frame_id: str, asset_type: str) -> int:
    latest = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.frame_id == frame_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.version.desc()).first()
    return (latest.version + 1) if latest else 1


# -- Run creation -----------------------------------------------------------

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


# -- Image stage payload helpers -------------------------------------------

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


# -- Image stage ------------------------------------------------------------

def mark_image_stage_submitted(db: Session, run: VideoProductionRun, stage_task_id: str, model_trace: dict) -> VideoProductionRun:
    run.status = "image_batch_running"
    run.current_stage = "image_generation"
    run.pixelle_stage_task_id = stage_task_id
    record_stage_task(run, "image_generation", stage_task_id)
    run.model_trace_json = {**model_trace, **(run.model_trace_json or {})}
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run


def mark_image_stage_assets(db: Session, run: VideoProductionRun, assets: list[dict], pixelle_task_id: str) -> list[VideoProductionAsset]:
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "image",
        VideoProductionAsset.pixelle_task_id == pixelle_task_id,
    ).all()
    if existing:
        return existing

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


async def start_image_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    assert_can_start_images(run)
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


# -- AI audit ---------------------------------------------------------------

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


def run_ai_audit_for_assets(db: Session, run: VideoProductionRun, assets: list[VideoProductionAsset]) -> list[VideoProductionAsset]:
    audit_model = {}
    try:
        from app.services.model_registry import get_model_for_scene
        audit_model = get_model_for_scene(db, "quality_audit")
    except Exception:
        pass

    if not audit_model or not audit_model.get("api_key"):
        try:
            audit_model = resolve_runtime_model_config(db, "quality_audit")
        except Exception:
            audit_model = {}

    for asset in assets:
        existing_review = db.query(VideoReviewRecord).filter(
            VideoReviewRecord.asset_id == asset.id,
            VideoReviewRecord.review_type == "ai",
        ).first()
        if existing_review:
            continue

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

    if assets:
        recompute_run_gate(db, run.id, assets[0].asset_type)
    return assets


# -- Human review actions ---------------------------------------------------

def latest_approved_assets_by_frame(db: Session, run_id: str, asset_type: str = "image") -> dict[str, VideoProductionAsset]:
    latest = latest_assets_by_frame(db, run_id, asset_type)
    return {frame_id: asset for frame_id, asset in latest.items() if asset.status == "approved"}


def approve_asset(db: Session, asset_id: str, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")

    if asset.asset_type == "final_video":
        return approve_final_video_asset(db, asset, reviewer_user_id, comment)

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
    recompute_run_gate(db, asset.run_id, asset.asset_type)
    return asset


def reject_asset(db: Session, asset_id: str, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")

    if asset.asset_type == "final_video":
        return reject_final_video_asset(db, asset, reviewer_user_id, comment)

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
    recompute_run_gate(db, asset.run_id, asset.asset_type)
    return asset


# -- Video stage payload helpers --------------------------------------------

def video_stage_frames(db: Session, run: VideoProductionRun) -> list[dict]:
    latest_images = latest_assets_by_frame(db, run.id, "image")
    frames = (run.storyboard_json or {}).get("frames") or []
    payload = []
    for index, frame in enumerate(frames):
        frame_id = _frame_id(frame, index)
        image = latest_images.get(frame_id)
        if not image or image.status != "approved":
            raise VideoProductionError(f"Approved image missing for frame {frame_id}")
        payload.append({
            "frame_id": frame_id,
            "approved_image_url": image.url,
            "video_prompt": frame.get("video_prompt") or frame.get("image_prompt", ""),
            "reference_urls": frame.get("reference_urls") or [],
            "duration": float(frame.get("duration") or 5),
            "audio_mode": frame.get("audio_mode") or "tts",
        })
    return payload


def video_stage_frame_for_asset(db: Session, run: VideoProductionRun, frame_id: str) -> dict:
    for frame in video_stage_frames(db, run):
        if frame["frame_id"] == frame_id:
            return frame
    raise VideoProductionError(f"Frame not found for video regeneration: {frame_id}")


# -- Video stage ------------------------------------------------------------

def mark_video_stage_assets(db: Session, run: VideoProductionRun, assets: list[dict], pixelle_task_id: str) -> list[VideoProductionAsset]:
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "video_segment",
        VideoProductionAsset.pixelle_task_id == pixelle_task_id,
    ).all()
    if existing:
        return existing

    saved = []
    for item in assets:
        frame_id = item["frame_id"]
        asset = VideoProductionAsset(
            run_id=run.id,
            episode_id=run.episode_id,
            frame_id=frame_id,
            asset_type="video_segment",
            stage="video_rendering",
            url=item.get("url", ""),
            local_path=item.get("local_path", ""),
            thumbnail_url=item.get("thumbnail_url", ""),
            duration_seconds=(item.get("metadata") or {}).get("duration"),
            version=_next_asset_version(db, run.id, frame_id, "video_segment"),
            metadata_json={
                **(item.get("metadata") or {}),
                "error_code": item.get("error_code"),
                "message": item.get("message"),
                "retryable": item.get("retryable", True),
            },
            status="failed" if item.get("status") == "failed" else "review_pending",
            pixelle_task_id=pixelle_task_id,
        )
        db.add(asset)
        saved.append(asset)
    run.status = "video_review_pending"
    run.current_stage = "video_review"
    run.updated_at = bj_now()
    db.commit()
    for asset in saved:
        db.refresh(asset)
    return saved


async def start_video_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    assert_can_start_videos(db, run)
    frames = video_stage_frames(db, run)
    model_config = resolve_runtime_model_config(db, "video_rendering")
    response = await submit_video_batch(
        db=db,
        run_id=run.id,
        frames=frames,
        model_config=model_config,
    )
    run.status = "video_batch_running"
    run.current_stage = "video_rendering"
    run.pixelle_stage_task_id = response["stage_task_id"]
    record_stage_task(run, "video_rendering", response["stage_task_id"])
    trace = run.model_trace_json or {}
    trace["video_rendering"] = redact_runtime_model_config(model_config)
    run.model_trace_json = trace
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run


async def sync_video_stage_results(db: Session, run_id: str) -> list[VideoProductionAsset]:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Video stage is not complete: {status.get('status')}")
    assets = mark_video_stage_assets(db, run, status.get("assets", []), pixelle_task_id=run.pixelle_stage_task_id)
    run_ai_audit_for_assets(db, run, assets)
    return assets


# -- Compose stage ----------------------------------------------------------

def compose_segments(db: Session, run: VideoProductionRun) -> list[dict]:
    latest_segments = latest_assets_by_frame(db, run.id, "video_segment")
    frames = (run.storyboard_json or {}).get("frames") or []
    segments = []
    for index, frame in enumerate(frames):
        frame_id = _frame_id(frame, index)
        segment = latest_segments.get(frame_id)
        if not segment or segment.status != "approved":
            raise VideoProductionError(f"Approved video segment missing for frame {frame_id}")
        segments.append({
            "frame_id": frame_id,
            "video_url": segment.url,
            "duration": float(segment.duration_seconds or frame.get("duration") or 5),
            "narration": frame.get("narration", ""),
        })
    return segments


def default_edit_manifest(run: VideoProductionRun) -> dict:
    existing = run.edit_manifest_json or {}
    if existing:
        return existing
    return {
        "subtitle_style": {"position": "bottom", "font_size": 42},
        "bgm_policy": {"mode": "auto", "volume": 0.18},
        "intro_outro": {"intro_enabled": False, "outro_enabled": False},
        "watermark": {"enabled": False},
        "output_spec": {"aspect_ratio": "9:16", "resolution": "1080x1920"},
    }


async def start_compose_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    assert_can_compose(db, run)
    segments = compose_segments(db, run)
    edit_manifest = default_edit_manifest(run)
    response = await submit_compose(
        db=db,
        run_id=run.id,
        segments=segments,
        edit_manifest=edit_manifest,
        model_config={"provider": "mock", "model": "compose"},
    )
    run.status = "composing"
    run.current_stage = "composition"
    run.pixelle_stage_task_id = response["stage_task_id"]
    record_stage_task(run, "composition", response["stage_task_id"])
    run.edit_manifest_json = edit_manifest
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run


# -- Final video writeback --------------------------------------------------

def complete_final_video(db: Session, run: VideoProductionRun, asset: VideoProductionAsset) -> VideoProductionAsset:
    from app.db_models import GeneratedVideo, Series

    duration = int(asset.duration_seconds or 0)
    episode = db.query(Episode).filter(Episode.id == run.episode_id).first()
    series = db.query(Series).filter(Series.id == run.series_id).first() if run.series_id else None
    title = (episode.title if episode and episode.title else series.title if series else "Generated video")
    keyword = title or run.id

    if episode:
        episode.video_url = asset.url
        episode.duration_seconds = duration or episode.duration_seconds
        episode.status = "done"

    video = db.query(GeneratedVideo).filter(GeneratedVideo.pixelle_task_id == run.id).first()
    if not video:
        video = GeneratedVideo(
            keyword=keyword,
            title=title,
            video_path=asset.local_path or asset.url,
            duration=duration,
            status="completed",
            pixelle_task_id=run.id,
        )
        db.add(video)
    else:
        video.video_path = asset.local_path or asset.url
        video.duration = duration
        video.status = "completed"

    run.status = "completed"
    run.current_stage = "completed"
    run.completed_at = bj_now()
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return asset


def approve_final_video_asset(db: Session, asset: VideoProductionAsset, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    latest = latest_assets_by_frame(db, asset.run_id, "final_video").get(asset.frame_id)
    if latest and latest.id != asset.id:
        raise VideoProductionError("A newer final video version exists. Reload before reviewing.")
    asset.status = "approved"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="approved",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
    ))
    db.flush()
    return complete_final_video(db, run, asset)


def reject_final_video_asset(db: Session, asset: VideoProductionAsset, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    latest = latest_assets_by_frame(db, asset.run_id, "final_video").get(asset.frame_id)
    if latest and latest.id != asset.id:
        raise VideoProductionError("A newer final video version exists. Reload before reviewing.")
    asset.status = "rejected"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="rejected",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
    ))
    run.status = "video_segments_approved"
    run.current_stage = "video_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return asset


def run_final_audit_for_asset(db: Session, run: VideoProductionRun, asset: VideoProductionAsset) -> VideoProductionAsset:
    try:
        audit_model = resolve_runtime_model_config(db, "quality_audit")
    except Exception:
        audit_model = {}

    if not audit_model or not audit_model.get("api_key"):
        result = {"score": 0.0, "pass_fail": False, "issues": ["Final audit model not configured"]}
    else:
        try:
            from app.routers.audit import _do_audit
            result = _do_audit(audit_model, asset.url, None)
        except Exception as exc:
            result = {"score": 0.0, "pass_fail": False, "issues": [str(exc)]}

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
        db.commit()
        return complete_final_video(db, run, asset)

    asset.status = "review_pending"
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return asset


def persist_final_video(db: Session, run: VideoProductionRun, item: dict) -> VideoProductionAsset:
    metadata = item.get("metadata") or {}
    duration = int(metadata.get("duration") or 0)
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "final_video",
        VideoProductionAsset.pixelle_task_id == run.pixelle_stage_task_id,
    ).first()
    if existing:
        return existing
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url=item.get("url", ""),
        local_path=item.get("local_path", ""),
        thumbnail_url=item.get("thumbnail_url", ""),
        duration_seconds=duration,
        version=_next_asset_version(db, run.id, "final", "final_video"),
        metadata_json=metadata,
        status="review_pending",
        pixelle_task_id=run.pixelle_stage_task_id,
    )
    db.add(asset)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return run_final_audit_for_asset(db, run, asset)


async def sync_compose_stage_results(db: Session, run_id: str) -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Compose stage is not complete: {status.get('status')}")
    final_assets = [item for item in status.get("assets", []) if item.get("asset_type") == "final_video"]
    if not final_assets:
        raise VideoProductionError("Compose stage returned no final video")
    return persist_final_video(db, run, final_assets[0])


# -- Single-item regeneration -----------------------------------------------

async def start_asset_regeneration(db: Session, asset_id: str) -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    frames = (run.storyboard_json or {}).get("frames") or []
    frame = next((item for index, item in enumerate(frames) if _frame_id(item, index) == asset.frame_id), None)
    if not frame:
        raise VideoProductionError("Frame not found in storyboard")

    if asset.asset_type == "image":
        model_config = resolve_runtime_model_config(db, "image_generation")
        response = await submit_image_batch(
            db=db,
            run_id=run.id,
            episode_id=run.episode_id,
            frames=[{
                "frame_id": asset.frame_id,
                "image_prompt": frame.get("image_prompt", ""),
                "reference_urls": frame.get("reference_urls") or [],
                "style_constraints": {
                    "character_ids": frame.get("character_ids") or [],
                    "scene_id": frame.get("scene_id"),
                    "continuity_notes": frame.get("continuity_notes", ""),
                },
                "duration": float(frame.get("duration") or 5),
            }],
            model_config=model_config,
        )
    elif asset.asset_type == "video_segment":
        model_config = resolve_runtime_model_config(db, "video_rendering")
        response = await submit_video_batch(
            db=db,
            run_id=run.id,
            frames=[video_stage_frame_for_asset(db, run, asset.frame_id)],
            model_config=model_config,
        )
    else:
        raise VideoProductionError(f"Unsupported regeneration asset type: {asset.asset_type}")

    asset.status = "regenerating"
    asset.pixelle_task_id = response["stage_task_id"]
    record_stage_task(run, f"regeneration:{asset.asset_type}:{asset.frame_id}", response["stage_task_id"])
    db.commit()
    db.refresh(asset)
    return asset


async def sync_regenerated_asset(db: Session, asset_id: str) -> VideoProductionAsset:
    old = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not old:
        raise VideoProductionError("Asset not found")
    if not old.pixelle_task_id:
        raise VideoProductionError("Asset has no regeneration task")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == old.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    status = await get_stage_task(db, old.pixelle_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Regeneration task is not complete: {status.get('status')}")
    generated = next((item for item in status.get("assets", []) if item.get("frame_id") == old.frame_id), None)
    if not generated:
        raise VideoProductionError("Regeneration returned no matching asset")
    old.status = "regenerating"
    new_asset = VideoProductionAsset(
        run_id=old.run_id,
        episode_id=old.episode_id,
        frame_id=old.frame_id,
        asset_type=old.asset_type,
        stage=old.stage,
        url=generated.get("url", ""),
        local_path=generated.get("local_path", ""),
        thumbnail_url=generated.get("thumbnail_url", ""),
        duration_seconds=(generated.get("metadata") or {}).get("duration"),
        version=_next_asset_version(db, old.run_id, old.frame_id, old.asset_type),
        metadata_json=generated.get("metadata", {}),
        status="review_pending",
        pixelle_task_id=old.pixelle_task_id,
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    run_ai_audit_for_assets(db, run, [new_asset])
    db.refresh(new_asset)
    return new_asset


# Legacy regeneration (manual payload) — kept for backward compat
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
