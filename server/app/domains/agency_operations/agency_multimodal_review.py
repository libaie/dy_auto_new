"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_multimodal_review 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Episode, VideoProductionAsset, VideoProductionRun
from app.domains.agency_operations.agency_orchestrator import AgencyOrchestrator
from app.domains.model_configuration.runtime_model_config import resolve_runtime_model_config


def build_multimodal_asset_context(db: Session, asset_id: str) -> dict[str, Any]:
    """业务函数：处理 build_multimodal_asset_context 对应的业务流程、校验或数据转换。

    入参：db、asset_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise ValueError("asset not found")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise ValueError("asset run not found")
    episode = db.query(Episode).filter(Episode.id == asset.episode_id).first()
    storyboard = (run.storyboard_json if run else None) or (episode.storyboard_json if episode else None) or {}
    frame = _frame_by_id(storyboard, asset.frame_id)
    media_inputs = _media_inputs_for_asset(asset)
    return {
        "run_id": asset.run_id,
        "episode_id": asset.episode_id,
        "asset": {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "stage": asset.stage,
            "url": asset.url,
            "thumbnail_url": asset.thumbnail_url,
            "frame_id": asset.frame_id,
            "status": asset.status,
            "version": asset.version,
            "production_segment_id": asset.production_segment_id,
            "target_type": asset.target_type,
            "target_id": asset.target_id,
        },
        "storyboard_frame": frame,
        "asset_review": {
            "media_inputs": media_inputs,
            "original_prompt": frame.get("image_prompt") if asset.asset_type == "image" else frame.get("video_prompt"),
            "review_instruction": (
                "Review the real generated asset for identity consistency, visual impact, motion rhythm, "
                "and short-video readiness. Use creative_patches for concrete repair proposals."
            ),
        },
    }


async def run_multimodal_asset_review(
    db: Session,
    asset_id: str,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """业务函数：处理 run_multimodal_asset_review 对应的业务流程、校验或数据转换。

    入参：db、asset_id、runtime_config 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise ValueError("asset not found")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise ValueError("asset run not found")

    resolved_config = runtime_config or resolve_runtime_model_config(db, "llm_agency_expert_review")
    context = build_multimodal_asset_context(db, asset_id)
    kwargs = {
        "series_id": run.series_id,
        "episode_id": asset.episode_id,
        "run_id": run.id,
        "production_plan_id": run.production_plan_id,
        "production_episode_id": run.production_episode_id,
        "production_segment_id": asset.production_segment_id,
        "stage_context": context,
        "runtime_config": resolved_config,
    }
    orchestrator = AgencyOrchestrator()
    if asset.asset_type == "image":
        return await orchestrator.run_image_review(db, **kwargs)
    return await orchestrator.run_video_review(db, **kwargs)


def _frame_by_id(storyboard: dict[str, Any], frame_id: str) -> dict[str, Any]:
    """业务函数：处理 _frame_by_id 对应的业务流程、校验或数据转换。

    入参：storyboard、frame_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    for frame in storyboard.get("frames") or []:
        if str(frame.get("frame_id") or frame.get("shot_id") or "") == frame_id:
            return frame
    return {}


def _media_inputs_for_asset(asset: VideoProductionAsset) -> list[dict[str, str]]:
    """业务函数：处理 _media_inputs_for_asset 对应的业务流程、校验或数据转换。

    入参：asset 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    media_inputs = []
    if asset.asset_type == "image" and asset.url:
        media_inputs.append({"type": "image_url", "url": asset.url})
    if asset.asset_type != "image" and asset.url:
        media_inputs.append({"type": "video_url", "url": asset.url})
    thumbnail_url = asset.thumbnail_url or ((asset.metadata_json or {}).get("thumbnail_url") if asset.metadata_json else None)
    if thumbnail_url:
        media_inputs.append({"type": "image_url", "url": thumbnail_url})
    return media_inputs
