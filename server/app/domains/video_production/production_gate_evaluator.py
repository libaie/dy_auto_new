"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_gate_evaluator 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.video_production import VideoProductionAsset, VideoProductionRun
from app.domains.production_observability.production_observability_service import record_production_event
from app.domains.video_production.video_production_state import production_segment_frame_ids


STAGE_ASSET_TYPES = {
    "image_generation": "image",
    "video_generation": "video_segment",
    "episode_compose": "final_video",
}


def _asset_type_for_stage(stage: str) -> str:
    """业务函数：处理 _asset_type_for_stage 对应的业务流程、校验或数据转换。"""
    try:
        return STAGE_ASSET_TYPES[stage]
    except KeyError as exc:
        raise ValueError(f"Unsupported stage gate: {stage}") from exc


def _required_ids(db: Session, run: VideoProductionRun, asset_type: str) -> list[str]:
    """业务函数：处理 _required_ids 对应的业务流程、校验或数据转换。"""
    if asset_type == "final_video":
        return ["final"]
    return production_segment_frame_ids(db, run)


def _latest_assets_by_required_id(
    db: Session,
    run: VideoProductionRun,
    asset_type: str,
) -> dict[str, VideoProductionAsset]:
    """业务函数：处理 _latest_assets_by_required_id 对应的业务流程、校验或数据转换。"""
    rows = (
        db.query(VideoProductionAsset)
        .filter(
            VideoProductionAsset.run_id == run.id,
            VideoProductionAsset.asset_type == asset_type,
            VideoProductionAsset.is_latest.is_(True),
        )
        .order_by(VideoProductionAsset.version.desc(), VideoProductionAsset.created_at.desc())
        .all()
    )
    latest: dict[str, VideoProductionAsset] = {}
    for asset in rows:
        required_id = "final" if asset_type == "final_video" else (asset.production_segment_id or asset.frame_id)
        latest.setdefault(required_id, asset)
    return latest


def _blocked_reason(asset: VideoProductionAsset | None) -> str | None:
    """业务函数：处理 _blocked_reason 对应的业务流程、校验或数据转换。"""
    if asset is None:
        return "asset_missing"
    if asset.status != "approved":
        return "asset_not_approved"
    if asset.copy_status != "persisted" or not asset.checksum or not asset.storage_path:
        return "asset_not_persisted"
    return None


def evaluate_stage_gate(db: Session, run_id: str, *, stage: str) -> dict:
    """业务函数：处理 evaluate_stage_gate 对应的业务流程、校验或数据转换。"""
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).one()
    asset_type = _asset_type_for_stage(stage)
    required_ids = _required_ids(db, run, asset_type)
    latest = _latest_assets_by_required_id(db, run, asset_type)

    approved_count = 0
    blocked_details = []
    for required_id in required_ids:
        asset = latest.get(required_id)
        reason = _blocked_reason(asset)
        if reason:
            blocked_details.append(
                {
                    "required_id": required_id,
                    "segment_id": None if asset_type == "final_video" else required_id,
                    "asset_id": asset.id if asset else None,
                    "asset_status": asset.status if asset else None,
                    "copy_status": asset.copy_status if asset else None,
                    "is_latest": bool(asset.is_latest) if asset else False,
                    "reason": reason,
                }
            )
        else:
            approved_count += 1

    blocked_segment_ids = [
        detail["required_id"]
        for detail in blocked_details
        if asset_type != "final_video"
    ]
    result = {
        "ready": not blocked_details,
        "status": "ready" if not blocked_details else "blocked",
        "stage": stage,
        "asset_type": asset_type,
        "required_count": len(required_ids),
        "approved_count": approved_count,
        "blocked_segment_ids": blocked_segment_ids,
        "blocked_details": blocked_details,
    }
    record_production_event(
        db,
        event_type="gate.evaluated",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        payload=result,
    )
    db.flush()
    return result
