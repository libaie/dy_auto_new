"""Review asset edit helpers for the video production domain."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.video_production import VideoProductionAsset, VideoReviewRecord


@dataclass
class ReviewAssetEditError(ValueError):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


VOIDABLE_STATUSES = {"review_pending", "rejected", "failed", "regenerating"}
EDITABLE_IMAGE_STATUSES = {"review_pending", "rejected", "failed"}
USABLE_IMAGE_CREATION_STATUSES = {"generated", "review_pending", "approved"}
FAILED_IMAGE_TASK_STATUSES = {"failed", "blocked", "rejected", "error"}


def _asset_snapshot(asset: VideoProductionAsset) -> dict[str, Any]:
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
        "duration_seconds": asset.duration_seconds,
        "version": asset.version,
        "status": asset.status,
        "is_latest": asset.is_latest,
        "target_type": asset.target_type,
        "target_id": asset.target_id,
        "production_segment_id": asset.production_segment_id,
        "production_shot_id": asset.production_shot_id,
        "metadata_json": asset.metadata_json or {},
    }


def _load_asset(db: Session, asset_id: str) -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise ReviewAssetEditError("ASSET_NOT_FOUND", "Asset not found")
    return asset


def _assert_latest(asset: VideoProductionAsset, expected_version: int | None) -> None:
    if expected_version is not None and asset.version != expected_version:
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "The submitted asset version is no longer current")
    if not asset.is_latest:
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "Only the latest asset version can be changed")


def _assert_image_editable(asset: VideoProductionAsset) -> None:
    if asset.status in {"regenerating"}:
        raise ReviewAssetEditError(
            "IMAGE_EDIT_IN_PROGRESS",
            "An image edit or regeneration is already in progress for this asset.",
            {"status": asset.status},
        )
    if asset.status not in EDITABLE_IMAGE_STATUSES:
        raise ReviewAssetEditError(
            "IMAGE_EDIT_STATUS_NOT_EDITABLE",
            f"Asset status is not editable: {asset.status}",
            {"status": asset.status},
        )


def _reserve_image_edit(
    db: Session,
    asset: VideoProductionAsset,
    expected_version: int | None,
) -> None:
    filters = [
        VideoProductionAsset.id == asset.id,
        VideoProductionAsset.asset_type == "image",
        VideoProductionAsset.is_latest.is_(True),
        VideoProductionAsset.status.in_(EDITABLE_IMAGE_STATUSES),
    ]
    if expected_version is not None:
        filters.append(VideoProductionAsset.version == expected_version)

    updated = db.query(VideoProductionAsset).filter(*filters).update(
        {"status": "regenerating", "updated_at": bj_now()},
        synchronize_session=False,
    )
    if updated != 1:
        db.rollback()
        current = _load_asset(db, asset.id)
        _assert_latest(current, expected_version)
        _assert_image_editable(current)
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "A newer asset version already exists")

    db.commit()
    db.refresh(asset)


def void_asset_version(
    db: Session,
    asset_id: str,
    reviewer_user_id: str | None = None,
    comment: str = "",
    expected_version: int | None = None,
) -> dict[str, Any]:
    asset = _load_asset(db, asset_id)
    _assert_latest(asset, expected_version)
    if asset.status not in VOIDABLE_STATUSES:
        raise ReviewAssetEditError(
            "ASSET_STATUS_NOT_VOIDABLE",
            f"Asset status is not voidable: {asset.status}",
            {"status": asset.status},
        )

    asset.status = "voided"
    asset.updated_at = bj_now()
    review = VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="voided",
        reviewer_user_id=reviewer_user_id,
        action="void",
        comment=comment,
        asset_snapshot_json=_asset_snapshot(asset),
        asset_version=asset.version,
        is_latest_asset_review=True,
        target_type=asset.target_type,
        target_id=asset.target_id,
        production_segment_id=asset.production_segment_id,
    )
    db.add(review)
    db.commit()
    db.refresh(asset)
    db.refresh(review)
    return {"ok": True, "asset": asset, "review_id": review.id}


def _provider_failure(exc: HTTPException) -> ReviewAssetEditError:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    code = detail.get("error_code") or detail.get("code") or "IMAGE_EDIT_PROVIDER_FAILED"
    message = detail.get("message") or "Image edit provider request failed."
    return ReviewAssetEditError(
        "IMAGE_EDIT_PROVIDER_FAILED",
        message,
        {"provider_code": code, "status_code": exc.status_code, "detail": detail},
    )


def _edit_idempotency_key(asset: VideoProductionAsset, instruction: str) -> str:
    instruction_hash = hashlib.sha256(instruction.encode("utf-8")).hexdigest()
    return f"video-review-edit:{asset.id}:{asset.version}:{instruction_hash}"


def _raise_failed_task(task) -> None:
    if task.status in FAILED_IMAGE_TASK_STATUSES or task.error_code:
        raise ReviewAssetEditError(
            "IMAGE_EDIT_PROVIDER_FAILED",
            task.error_message or "Image edit task failed before producing a usable image.",
            {
                "image_task_id": task.id,
                "status": task.status,
                "error_code": task.error_code,
                "error_message": task.error_message,
            },
        )


async def _generate_edited_image(db: Session, asset: VideoProductionAsset, instruction: str) -> dict[str, Any]:
    from app.db.models import ImageCreationAsset
    from app.domains.image_generation.image_creation_service import create_image_task, sync_image_task

    payload = {
        "mode": "image_to_image",
        "prompt": instruction,
        "source": {"type": "url", "url": asset.source_url or asset.url},
        "source_url": asset.source_url or asset.url,
        "count": 1,
        "destination_role": "video_production_review_edit",
        "destination_context": {
            "video_asset_id": asset.id,
            "run_id": asset.run_id,
            "episode_id": asset.episode_id,
            "frame_id": asset.frame_id,
            "asset_type": asset.asset_type,
            "asset_version": asset.version,
            "production_segment_id": asset.production_segment_id,
        },
        "idempotency_key": _edit_idempotency_key(asset, instruction),
        "cost_confirmation": True,
    }
    try:
        task = await create_image_task(db, payload)
    except HTTPException as exc:
        raise _provider_failure(exc) from exc

    _raise_failed_task(task)
    has_provider_id = bool(task.pixelle_task_id or task.provider_task_id)
    if task.status == "queued" and not has_provider_id:
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_QUEUED",
            "Image edit task is queued and waiting for provider submission.",
            {"image_task_id": task.id, "status": task.status},
        )
    if has_provider_id:
        try:
            task = await sync_image_task(db, task.id)
        except HTTPException as exc:
            raise _provider_failure(exc) from exc
        _raise_failed_task(task)

    image_asset = (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.task_id == task.id)
        .filter(ImageCreationAsset.status.in_(USABLE_IMAGE_CREATION_STATUSES))
        .filter(ImageCreationAsset.url.isnot(None))
        .order_by(ImageCreationAsset.is_latest.desc(), ImageCreationAsset.version.desc(), ImageCreationAsset.created_at.desc())
        .first()
    )
    if not image_asset or not image_asset.url:
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_PENDING",
            "Image edit task has not produced a usable image URL yet.",
            {"image_task_id": task.id, "status": task.status},
        )

    return {
        "url": image_asset.url,
        "source_url": image_asset.source_url or asset.url,
        "image_creation_task_id": task.id,
        "image_creation_asset_id": image_asset.id,
        "local_path": image_asset.local_path,
        "thumbnail_url": image_asset.thumbnail_url,
        "storage_path": image_asset.storage_path,
        "copy_status": image_asset.storage_status,
        "checksum": image_asset.checksum,
        "size_bytes": image_asset.size_bytes,
        "provider_task_id": image_asset.provider_task_id or task.provider_task_id,
        "pixelle_task_id": image_asset.pixelle_task_id or task.pixelle_task_id,
        "provider_response_summary_json": {
            "image_creation_task_status": task.status,
            "provider": image_asset.provider or task.provider,
            "model_id": image_asset.model_id or task.model_id,
        },
    }


async def edit_image_asset(
    db: Session,
    asset_id: str,
    instruction: str,
    expected_version: int | None = None,
) -> dict[str, Any]:
    clean_instruction = instruction.strip()
    asset = _load_asset(db, asset_id)
    if asset.asset_type != "image":
        raise ReviewAssetEditError("IMAGE_EDIT_UNSUPPORTED", "Only image assets can be edited")
    _assert_latest(asset, expected_version)
    _assert_image_editable(asset)

    original_status = asset.status
    _reserve_image_edit(db, asset, expected_version)

    try:
        generated = await _generate_edited_image(db, asset, clean_instruction)
    except Exception:
        db.rollback()
        current = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset.id).first()
        if current and current.is_latest and current.status == "regenerating":
            current.status = original_status
            current.updated_at = bj_now()
            db.commit()
        raise

    latest_query = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == asset.run_id,
        VideoProductionAsset.frame_id == asset.frame_id,
        VideoProductionAsset.asset_type == asset.asset_type,
        VideoProductionAsset.is_latest.is_(True),
    )
    try:
        current_latest = latest_query.with_for_update().first()
    except Exception:
        current_latest = latest_query.first()
    if not current_latest or current_latest.id != asset.id:
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "A newer asset version already exists")

    latest_version = db.query(func.max(VideoProductionAsset.version)).filter(
        VideoProductionAsset.run_id == asset.run_id,
        VideoProductionAsset.frame_id == asset.frame_id,
        VideoProductionAsset.asset_type == asset.asset_type,
    ).scalar() or asset.version
    old_metadata = asset.metadata_json or {}
    new_metadata = {
        **old_metadata,
        "source_asset_id": asset.id,
        "source_version": asset.version,
        "edit_instruction": clean_instruction,
        "storyboard_frame": old_metadata.get("storyboard_frame"),
    }
    for key in ("image_creation_task_id", "image_creation_asset_id"):
        if generated.get(key):
            new_metadata[key] = generated[key]

    new_asset = VideoProductionAsset(
        run_id=asset.run_id,
        episode_id=asset.episode_id,
        frame_id=asset.frame_id,
        asset_type=asset.asset_type,
        stage=asset.stage,
        url=generated.get("url"),
        source_url=generated.get("source_url") or asset.url,
        local_path=generated.get("local_path") or asset.local_path,
        thumbnail_url=generated.get("thumbnail_url") or asset.thumbnail_url,
        duration_seconds=asset.duration_seconds,
        version=int(latest_version) + 1,
        metadata_json=new_metadata,
        status="review_pending",
        pixelle_task_id=generated.get("pixelle_task_id") or asset.pixelle_task_id,
        provider_task_id=generated.get("provider_task_id") or asset.provider_task_id,
        provider_stage_task_id=asset.provider_stage_task_id,
        provider_response_summary_json=generated.get("provider_response_summary_json") or {},
        production_segment_id=asset.production_segment_id,
        production_shot_id=asset.production_shot_id,
        target_type=asset.target_type,
        target_id=asset.target_id,
        storage_path=generated.get("storage_path"),
        storage_error_json={},
        is_latest=True,
        source_version=asset.version,
        copy_status=generated.get("copy_status") or asset.copy_status,
        checksum=generated.get("checksum"),
        size_bytes=generated.get("size_bytes"),
    )
    db.add(new_asset)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ReviewAssetEditError(
            "STALE_ASSET_VERSION",
            "Another edit created a newer asset version first.",
            {"run_id": asset.run_id, "frame_id": asset.frame_id, "asset_type": asset.asset_type},
        ) from exc

    asset.is_latest = False
    asset.updated_at = bj_now()
    db.commit()
    db.refresh(new_asset)
    db.refresh(asset)
    return {"ok": True, "asset": new_asset}
