from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db_models import ImageCreationAsset, ImageCreationTask, VideoProductionAsset, VideoProductionRun
from app.services.image_creation_errors import image_error
from app.services.image_creation_service import _asset_allowed_actions
from app.domains.image_generation.image_review_gate_service import asset_review_gate, review_gate_passed, review_gate_rescue_actions


def _review_snapshot(asset: ImageCreationAsset) -> dict[str, Any]:
    return {
        "status": asset.status,
        "audit_status": asset.audit_status,
        "ai_score": asset.ai_score,
        "ai_report": asset.ai_report_json or {},
        "manual_review_status": asset.manual_review_status,
    }


def _metadata(asset: ImageCreationAsset, task: ImageCreationTask | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_image_asset_id": asset.id,
        "source_image_task_id": asset.task_id,
        "source_image_version": asset.version,
        "strategy_snapshot": task.strategy_snapshot_json if task else {},
        "source_image_asset": {
            "id": asset.id,
            "version": asset.version,
            "slot_key": asset.slot_key,
            "destination_role": asset.destination_role,
            "destination_context": asset.destination_context_json or {},
            "metadata": asset.metadata_json or {},
        },
        "source_image_task": {
            "id": task.id,
            "mode": task.mode,
            "strategy_id": task.strategy_id,
            "strategy_version": task.strategy_version,
        } if task else None,
        "source_version": asset.version,
        "destination_role": payload.get("destination_role") or asset.destination_role,
        "review_snapshot": _review_snapshot(asset),
        "provider": asset.provider,
        "model_id": asset.model_id,
        "provider_task_id": asset.provider_task_id,
        "pixelle_task_id": asset.pixelle_task_id,
        "checksum": asset.checksum,
        "size_bytes": asset.size_bytes,
        "width": asset.width,
        "height": asset.height,
    }


def _scope_conflict(message: str, affected_ids: list[str]) -> None:
    raise image_error(
        409,
        "IMAGE_ASSET_SCOPE_CONFLICT",
        message,
        "Choose an approved image asset from the same video production scope.",
        retryable=False,
        affected_ids=affected_ids,
    )


def _validate_scope(asset: ImageCreationAsset, task: ImageCreationTask | None, run: VideoProductionRun, payload: dict[str, Any]) -> None:
    user_id = payload.get("user_id")
    for source_user_id in [asset.user_id, task.user_id if task else None]:
        if source_user_id and source_user_id != user_id:
            _scope_conflict("Image asset belongs to another user scope.", [asset.id, run.id])

    if payload.get("episode_id") and payload["episode_id"] != run.episode_id:
        _scope_conflict("Requested episode does not match the video production run.", [asset.id, run.id])

    for source_series_id in [asset.series_id, task.series_id if task else None]:
        if source_series_id and run.series_id and source_series_id != run.series_id:
            _scope_conflict("Image asset series does not match the video production run.", [asset.id, run.id])

    for source_episode_id in [asset.episode_id, task.episode_id if task else None]:
        if source_episode_id and run.episode_id and source_episode_id != run.episode_id:
            _scope_conflict("Image asset episode does not match the video production run.", [asset.id, run.id])


def video_asset_payload(asset: VideoProductionAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "run_id": asset.run_id,
        "episode_id": asset.episode_id,
        "frame_id": asset.frame_id,
        "asset_type": asset.asset_type,
        "stage": asset.stage,
        "url": asset.url,
        "local_path": asset.local_path,
        "thumbnail_url": asset.thumbnail_url,
        "version": asset.version,
        "metadata_json": asset.metadata_json or {},
        "status": asset.status,
        "pixelle_task_id": asset.pixelle_task_id,
    }


def promote_image_asset_to_video_asset(
    db: Session,
    asset_id: str,
    payload: dict[str, Any],
) -> VideoProductionAsset:
    asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
    if not asset:
        raise image_error(
            404,
            "SOURCE_ASSET_NOT_FOUND",
            "Source image asset not found.",
            "Pick another image asset.",
            retryable=False,
        )
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == asset.task_id).first()
    asset_version = payload.get("asset_version")
    if asset_version is not None and int(asset_version) != asset.version:
        raise image_error(
            409,
            "STALE_ASSET_VERSION",
            "This promotion targets an older asset version.",
            "Reload latest asset.",
            retryable=False,
            affected_ids=[asset.id],
        )
    if not review_gate_passed(task, asset):
        raise image_error(
            409,
            "IMAGE_REVIEW_GATE_BLOCKED",
            "Image asset is blocked by the review gate.",
            "Complete image review before promotion.",
            retryable=False,
            affected_ids=[asset.id],
            details={"review_gate": asset_review_gate(task, asset)},
            rescue_actions=review_gate_rescue_actions(asset),
        )
    if "promote_to_video_asset" not in _asset_allowed_actions(asset, task):
        raise image_error(
            409,
            "IMAGE_ASSET_ACTION_NOT_ALLOWED",
            "This asset cannot be promoted from its current production context.",
            "Reload the asset and choose an available action.",
            retryable=False,
            affected_ids=[asset.id],
            details={"allowed_actions": _asset_allowed_actions(asset, task)},
        )

    run_id = payload["run_id"]
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise image_error(
            404,
            "VIDEO_RUN_NOT_FOUND",
            "Video production run not found.",
            "Pick an existing video production run.",
            retryable=False,
        )
    _validate_scope(asset, task, run, payload)

    frame_id = payload["frame_id"]
    version = payload.get("version") or asset.version or 1
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.frame_id == frame_id,
        VideoProductionAsset.asset_type == "image",
        VideoProductionAsset.version == version,
    ).first()

    if existing:
        existing_source_asset_id = (existing.metadata_json or {}).get("source_image_asset_id")
        if existing_source_asset_id != asset.id:
            raise image_error(
                409,
                "VIDEO_ASSET_SLOT_CONFLICT",
                "A different image asset already occupies this video frame version.",
                "Use a new video asset version or choose another frame.",
                retryable=False,
                affected_ids=[existing.id, asset.id],
            )
        video_asset = existing
    else:
        video_asset = VideoProductionAsset(
            run_id=run.id,
            episode_id=payload.get("episode_id") or run.episode_id,
            frame_id=frame_id,
            asset_type="image",
            stage="image_review",
            url=asset.url,
            local_path=asset.local_path,
            thumbnail_url=asset.thumbnail_url,
            version=version,
            status="approved",
            metadata_json=_metadata(asset, task, payload),
            pixelle_task_id=asset.pixelle_task_id,
            provider_task_id=asset.provider_task_id,
            checksum=asset.checksum,
            size_bytes=asset.size_bytes,
            source_version=asset.version,
        )
        db.add(video_asset)
        db.flush()

    usage_entry = {
        "type": "video_production_asset",
        "run_id": run.id,
        "frame_id": frame_id,
        "version": version,
        "video_asset_id": video_asset.id,
    }
    usage = list(asset.downstream_usage_json or [])
    if usage_entry not in usage:
        usage.append(usage_entry)
        asset.downstream_usage_json = usage

    db.commit()
    db.refresh(video_asset)
    return video_asset
