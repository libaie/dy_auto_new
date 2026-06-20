from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.video_production import VideoProductionRun
from app.db_models import VideoProductionAsset, VideoReviewRecord
from app.domains.video_production.production_state_contract import asset_is_reviewable
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE, get_run_type
from app.domains.video_production.video_production_state import latest_assets_by_frame, recompute_run_gate


SUPPORTED_BULK_REVIEW_ACTIONS = {"approve", "reject"}
GATED_ASSET_TYPES = {"image", "video_segment"}
SUPPORTED_BULK_ASSET_TYPES = GATED_ASSET_TYPES


def _review_snapshot(asset: VideoProductionAsset) -> dict:
    return {
        "target_type": asset.target_type,
        "target_id": asset.target_id,
        "production_segment_id": asset.production_segment_id,
        "asset_version": asset.version,
        "is_latest_asset_review": bool(asset.is_latest),
    }


def _assert_bulk_approvable(asset: VideoProductionAsset) -> None:
    if not asset_is_reviewable(asset):
        raise ValueError("Bulk approve requires review_pending assets")
    if asset.copy_status != "persisted" or not asset.checksum or not asset.storage_path:
        raise ValueError("Bulk approve requires persisted assets")


def apply_bulk_review_action(
    db: Session,
    asset_ids: list[str],
    action: str,
    reviewer_user_id: str | None = None,
    comment: str = "",
) -> dict:
    if action not in SUPPORTED_BULK_REVIEW_ACTIONS:
        raise ValueError(f"Unsupported review action: {action}")

    approved = 0
    rejected = 0
    skipped_stale = 0
    review_status = "approved" if action == "approve" else "rejected"
    gate_targets: set[tuple[str, str]] = set()
    seen_asset_ids: set[str] = set()
    batch_gate_types: dict[str, str] = {}
    valid_assets: list[VideoProductionAsset] = []

    for asset_id in asset_ids:
        if asset_id in seen_asset_ids:
            continue
        seen_asset_ids.add(asset_id)

        asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
        if not asset:
            continue

        if asset.asset_type == "final_video":
            raise ValueError("Final video requires manual final review approval")
        if asset.asset_type not in SUPPORTED_BULK_ASSET_TYPES:
            raise ValueError(f"Unsupported bulk review asset type: {asset.asset_type}")
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
        if not run or get_run_type(run) != MOCK_SERIES_SCALE:
            raise ValueError("Bulk review is only available for mock_series_scale image and video segment assets")

        previous_asset_type = batch_gate_types.setdefault(asset.run_id, asset.asset_type)
        if previous_asset_type != asset.asset_type:
            raise ValueError("Bulk review cannot mix asset types for the same run")

        latest = latest_assets_by_frame(db, asset.run_id, asset.asset_type).get(asset.frame_id)
        if latest and latest.id != asset.id:
            skipped_stale += 1
            continue

        if action == "approve":
            _assert_bulk_approvable(asset)

        valid_assets.append(asset)

    for asset in valid_assets:
        asset.status = review_status
        asset.updated_at = bj_now()
        if review_status == "approved":
            approved += 1
            score = 1.0
            issues = []
        else:
            rejected += 1
            score = 0.0
            issues = [comment or "Rejected by reviewer"]

        db.add(
            VideoReviewRecord(
                asset_id=asset.id,
                run_id=asset.run_id,
                review_type="human",
                status=review_status,
                score=score,
                issues_json=issues,
                reviewer_user_id=reviewer_user_id,
                comment=comment,
                **_review_snapshot(asset),
            )
        )
        if asset.asset_type in GATED_ASSET_TYPES:
            gate_targets.add((asset.run_id, asset.asset_type))

    db.commit()
    for run_id, asset_type in gate_targets:
        recompute_run_gate(db, run_id, asset_type)

    return {"approved": approved, "rejected": rejected, "skipped_stale": skipped_stale}
