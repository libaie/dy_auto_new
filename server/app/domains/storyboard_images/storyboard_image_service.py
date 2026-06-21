"""分镜图片业务域模块。

分镜图片业务域，负责分镜帧图片生成、绑定和状态查询。本文件负责 storyboard_image_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Episode, ImageCreationAsset, ImageCreationTask, Series, VideoProductionRun
from app.domains.image_generation.image_asset_bridge_service import promote_image_asset_to_video_asset, video_asset_payload
from app.domains.image_generation.image_creation_errors import image_error
from app.domains.image_generation.image_review_gate_service import review_gate_passed
from app.domains.image_generation.image_creation_service import asset_payload, create_image_task, task_payload


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _normalized_frame_id(frame: dict[str, Any], index: int) -> str:
    return str(frame.get("frame_id") or frame.get("shot_id") or frame.get("id") or f"frame-{index + 1:03d}")


def _storyboard_frames(storyboard: dict[str, Any] | None) -> list[dict[str, Any]]:
    frames = storyboard.get("frames") if isinstance(storyboard, dict) else []
    if not isinstance(frames, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            continue
        normalized.append({**frame, "frame_id": _normalized_frame_id(frame, index), "index": index})
    return normalized


def _load_storyboard_scope(
    db: Session,
    *,
    series_id: str,
    episode_id: str,
    run_id: str | None = None,
) -> tuple[Series, Episode, VideoProductionRun | None, list[dict[str, Any]]]:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise image_error(404, "SERIES_NOT_FOUND", "Series not found.", "Reload the series page.", retryable=False)
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise image_error(404, "EPISODE_NOT_FOUND", "Episode not found.", "Reload the series page.", retryable=False)
    run = None
    storyboard = episode.storyboard_json
    if run_id:
        run = db.query(VideoProductionRun).filter(
            VideoProductionRun.id == run_id,
            VideoProductionRun.series_id == series_id,
            VideoProductionRun.episode_id == episode_id,
        ).first()
        if not run:
            raise image_error(404, "VIDEO_RUN_NOT_FOUND", "Video production run not found.", "Reload the production monitor.", retryable=False)
        storyboard = run.storyboard_json or storyboard
    return series, episode, run, _storyboard_frames(storyboard)


def _find_frame(frames: list[dict[str, Any]], frame_id: str) -> dict[str, Any]:
    wanted = str(frame_id)
    for frame in frames:
        keys = {str(frame.get("frame_id") or ""), str(frame.get("shot_id") or ""), str(frame.get("id") or "")}
        if wanted in keys:
            return frame
    raise image_error(
        404,
        "STORYBOARD_FRAME_NOT_FOUND",
        "Storyboard frame was not found.",
        "Regenerate storyboard or refresh the page.",
        retryable=False,
        affected_ids=[wanted],
    )


def _frame_reference_images(frame: dict[str, Any]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(url: Any, role: str = "reference") -> None:
        clean = str(url or "").strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        images.append({"type": "url", "url": clean, "role": role})

    for item in frame.get("reference_roles") or []:
        if isinstance(item, dict):
            add(item.get("url"), str(item.get("role") or "reference"))
    for url in frame.get("reference_urls") or []:
        add(url, "reference")
    for url in frame.get("character_reference_urls") or []:
        add(url, "character")
    for url in frame.get("style_reference_urls") or []:
        add(url, "style")
    for item in frame.get("reference_images") or []:
        if isinstance(item, dict):
            add(item.get("url"), str(item.get("role") or "reference"))
        else:
            add(item, "reference")
    return images


def _task_idempotency_key(
    *,
    series_id: str,
    episode_id: str,
    frame_id: str,
    prompt: str,
    reference_images: list[dict[str, Any]],
    run_id: str | None = None,
) -> str:
    prompt_hash = _stable_hash({"prompt": prompt, "references": reference_images})
    if run_id:
        run_hash = _stable_hash({"run_id": run_id})
        return f"storyboard-frame-image:{series_id}:{episode_id}:{frame_id}:{run_hash}:{prompt_hash}:v1"
    return f"storyboard-frame-image:{series_id}:{episode_id}:{frame_id}:{prompt_hash}:v1"


def _existing_task_for_key(db: Session, idempotency_key: str) -> ImageCreationTask | None:
    return db.query(ImageCreationTask).filter(ImageCreationTask.idempotency_key == idempotency_key).first()


def _frame_payload(
    *,
    series_id: str,
    episode_id: str,
    run_id: str | None,
    frame: dict[str, Any],
    force: bool,
    count: int,
    size: str | None,
    user_id: str | None,
) -> dict[str, Any]:
    frame_id = str(frame["frame_id"])
    prompt = str(frame.get("image_prompt") or frame.get("visual_prompt") or "").strip()
    if not prompt:
        raise image_error(
            422,
            "STORYBOARD_IMAGE_PROMPT_MISSING",
            "Storyboard frame has no usable image prompt.",
            "Regenerate or refine the storyboard prompt.",
            retryable=False,
            affected_ids=[frame_id],
        )
    reference_images = _frame_reference_images(frame)
    idempotency_key = _task_idempotency_key(
        series_id=series_id,
        episode_id=episode_id,
        frame_id=frame_id,
        prompt=prompt,
        reference_images=reference_images,
        run_id=run_id,
    )
    if force:
        idempotency_key = f"{idempotency_key}:force:{uuid.uuid4().hex}"
    return {
        "mode": "text_to_image",
        "prompt": prompt,
        "negative_prompt": str(frame.get("negative_prompt") or ""),
        "reference_images": reference_images,
        "destination_role": "storyboard_frame",
        "destination_context": {
            "series_id": series_id,
            "episode_id": episode_id,
            "run_id": run_id or "",
            "frame_id": frame_id,
            "time_range": str(frame.get("time_range") or ""),
            "source": "storyboard_image",
        },
        "series_id": series_id,
        "episode_id": episode_id,
        "count": max(1, int(count or 1)),
        "size": size,
        "idempotency_key": idempotency_key,
        "cost_confirmation": True,
        "user_id": user_id,
    }


def _frame_result(frame: dict[str, Any], *, status: str, task: ImageCreationTask | None = None, error: Any = None) -> dict[str, Any]:
    result = {
        "frame_id": frame["frame_id"],
        "time_range": frame.get("time_range") or "",
        "status": status,
    }
    if task:
        result["task"] = task_payload(task)
    if error:
        result["error"] = error
    return result


async def create_storyboard_frame_image_task(
    db: Session,
    *,
    series_id: str,
    episode_id: str,
    frame_id: str,
    run_id: str | None = None,
    force: bool = False,
    count: int = 1,
    size: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    _, _, _, frames = _load_storyboard_scope(db, series_id=series_id, episode_id=episode_id, run_id=run_id)
    frame = _find_frame(frames, frame_id)
    payload = _frame_payload(
        series_id=series_id,
        episode_id=episode_id,
        run_id=run_id,
        frame=frame,
        force=force,
        count=count,
        size=size,
        user_id=user_id,
    )
    existing = None if force else _existing_task_for_key(db, payload["idempotency_key"])
    if existing:
        return {"ok": True, "frame": _frame_result(frame, status="skipped", task=existing), "task": task_payload(existing)}
    task = await create_image_task(db, payload)
    return {"ok": True, "frame": _frame_result(frame, status="created", task=task), "task": task_payload(task)}


async def create_missing_storyboard_image_tasks(
    db: Session,
    *,
    series_id: str,
    episode_id: str,
    run_id: str | None = None,
    force: bool = False,
    count: int = 1,
    size: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    _, _, _, frames = _load_storyboard_scope(db, series_id=series_id, episode_id=episode_id, run_id=run_id)
    results: list[dict[str, Any]] = []
    summary = {"created": 0, "skipped": 0, "failed": 0}
    for frame in frames:
        try:
            payload = _frame_payload(
                series_id=series_id,
                episode_id=episode_id,
                run_id=run_id,
                frame=frame,
                force=force,
                count=count,
                size=size,
                user_id=user_id,
            )
            existing = None if force else _existing_task_for_key(db, payload["idempotency_key"])
            if existing:
                summary["skipped"] += 1
                results.append(_frame_result(frame, status="skipped", task=existing))
                continue
            task = await create_image_task(db, payload)
            summary["created"] += 1
            results.append(_frame_result(frame, status="created", task=task))
        except Exception as exc:
            summary["failed"] += 1
            detail = getattr(exc, "detail", None)
            results.append(_frame_result(frame, status="failed", error=detail or {"message": str(exc)}))
    return {"ok": True, "summary": summary, "results": results}


def _context_matches_run(context: dict[str, Any] | None, run_id: str | None) -> bool:
    if not run_id:
        return True
    return str((context or {}).get("run_id") or "") == str(run_id)


def _context_matches_storyboard_frame(context: dict[str, Any] | None, *, run_id: str, frame_id: str) -> bool:
    if not isinstance(context, dict):
        return False
    return (
        str(context.get("run_id") or "") == str(run_id)
        and str(context.get("frame_id") or "") == str(frame_id)
    )


def _latest_tasks_by_frame(db: Session, *, series_id: str, episode_id: str, run_id: str | None = None) -> dict[str, ImageCreationTask]:
    rows = (
        db.query(ImageCreationTask)
        .filter(ImageCreationTask.series_id == series_id)
        .filter(ImageCreationTask.episode_id == episode_id)
        .filter(ImageCreationTask.destination_role == "storyboard_frame")
        .order_by(ImageCreationTask.created_at.desc())
        .all()
    )
    by_frame: dict[str, ImageCreationTask] = {}
    for task in rows:
        if not _context_matches_run(task.destination_context_json, run_id):
            continue
        frame_id = str((task.destination_context_json or {}).get("frame_id") or "")
        if frame_id and frame_id not in by_frame:
            by_frame[frame_id] = task
    return by_frame


def _latest_assets_by_frame(db: Session, *, series_id: str, episode_id: str, run_id: str | None = None) -> dict[str, ImageCreationAsset]:
    rows = (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.series_id == series_id)
        .filter(ImageCreationAsset.episode_id == episode_id)
        .filter(ImageCreationAsset.destination_role == "storyboard_frame")
        .order_by(ImageCreationAsset.created_at.desc())
        .all()
    )
    by_frame: dict[str, ImageCreationAsset] = {}
    for asset in rows:
        if not _context_matches_run(asset.destination_context_json, run_id):
            continue
        frame_id = str((asset.destination_context_json or {}).get("frame_id") or "")
        if frame_id and frame_id not in by_frame:
            by_frame[frame_id] = asset
    return by_frame


def _state_for(task: ImageCreationTask | None, asset: ImageCreationAsset | None) -> str:
    if asset:
        if asset.status == "approved":
            return "approved"
        if asset.status in {"rejected", "blocked", "failed"}:
            return "blocked"
        return "pending"
    if task:
        if task.status in {"queued", "running"}:
            return "running"
        if task.status in {"failed", "cancelled"}:
            return "blocked"
        return "pending"
    return "missing"


def list_storyboard_image_state(
    db: Session,
    *,
    series_id: str,
    episode_id: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    _, _, _, frames = _load_storyboard_scope(db, series_id=series_id, episode_id=episode_id, run_id=run_id)
    tasks_by_frame = _latest_tasks_by_frame(db, series_id=series_id, episode_id=episode_id, run_id=run_id)
    assets_by_frame = _latest_assets_by_frame(db, series_id=series_id, episode_id=episode_id, run_id=run_id)
    summary = {"total": len(frames), "approved": 0, "pending": 0, "running": 0, "missing": 0, "blocked": 0}
    frame_states: list[dict[str, Any]] = []
    for frame in frames:
        frame_id = str(frame["frame_id"])
        task = tasks_by_frame.get(frame_id)
        asset = assets_by_frame.get(frame_id)
        status = _state_for(task, asset)
        summary[status] += 1
        frame_state = {
            "frame_id": frame_id,
            "time_range": frame.get("time_range") or "",
            "status": status,
            "task": task_payload(task) if task else None,
            "asset": asset_payload(asset) if asset else None,
        }
        frame_states.append(frame_state)
    return {
        "ok": True,
        "series_id": series_id,
        "episode_id": episode_id,
        "run_id": run_id,
        "summary": summary,
        "frames": frame_states,
        "frames_by_id": {frame["frame_id"]: frame for frame in frame_states},
    }


def promote_storyboard_image_asset(
    db: Session,
    *,
    asset_id: str,
    run_id: str,
    frame_id: str,
    episode_id: str | None = None,
    asset_version: int | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
    if not asset:
        raise image_error(404, "SOURCE_ASSET_NOT_FOUND", "Source image asset not found.", "Pick another image asset.", retryable=False)
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == asset.task_id).first()
    if not review_gate_passed(task, asset):
        raise image_error(
            409,
            "STORYBOARD_IMAGE_REVIEW_REQUIRED",
            "Storyboard image must be approved before it can be used for video production.",
            "Complete image review.",
            retryable=False,
            affected_ids=[asset.id],
        )
    if not _context_matches_storyboard_frame(asset.destination_context_json, run_id=run_id, frame_id=frame_id) or (
        task is not None and not _context_matches_storyboard_frame(task.destination_context_json, run_id=run_id, frame_id=frame_id)
    ):
        raise image_error(
            409,
            "IMAGE_ASSET_SCOPE_CONFLICT",
            "Storyboard image asset does not belong to the requested production run and frame.",
            "Choose an approved image asset from the same video production scope.",
            retryable=False,
            affected_ids=[asset.id, run_id, frame_id],
        )
    context = dict(asset.destination_context_json or {})
    context["run_id"] = run_id
    context["frame_id"] = frame_id
    asset.destination_context_json = context
    payload = {
        "run_id": run_id,
        "frame_id": frame_id,
        "episode_id": episode_id or asset.episode_id,
        "asset_version": asset_version,
        "destination_role": "storyboard_frame",
        "user_id": user_id,
    }
    video_asset = promote_image_asset_to_video_asset(db, asset_id, payload)
    return {"ok": True, "video_asset": video_asset_payload(video_asset)}
