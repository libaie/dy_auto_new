"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 read_models 相关业务规则、状态转换和外部系统边界。
"""

from sqlalchemy.orm import Session

from app.db.models.ai_video_series import Episode, Series, VideoProductionRun
from app.db.models.video_library import GeneratedVideo
from app.db.models import Character, PipelineRun, Scene
from app.domains.agency_operations.agency_console import build_agency_console_payload
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
from app.domains.creative_library.reference_asset_service import reference_url_is_usable


VIDEO_RUN_TERMINAL_STATUSES = {"completed", "done", "failed", "cancelled", "canceled"}


def series_char_dict(c: Character) -> dict:
    """业务函数：处理 series_char_dict 对应的业务流程、校验或数据转换。

    入参：c 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {col.name: getattr(c, col.name) for col in Character.__table__.columns}


def series_scene_dict(s: Scene) -> dict:
    """业务函数：处理 series_scene_dict 对应的业务流程、校验或数据转换。

    入参：s 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {col.name: getattr(s, col.name) for col in Scene.__table__.columns}


def series_dict(s: Series, include_linked_assets: bool = False) -> dict:
    """业务函数：处理 series_dict 对应的业务流程、校验或数据转换。

    入参：s、include_linked_assets 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    base = {col.name: getattr(s, col.name) for col in Series.__table__.columns}
    base["character_count"] = len(s.characters) if hasattr(s, "characters") else 0
    base["scene_count"] = len(s.scenes) if hasattr(s, "scenes") else 0
    if include_linked_assets:
        base["characters"] = [series_char_dict(c) for c in (s.characters or [])]
        base["scenes"] = [series_scene_dict(scene) for scene in (s.scenes or [])]
    return base


def episode_dict(e: Episode) -> dict:
    """业务函数：处理 episode_dict 对应的业务流程、校验或数据转换。

    入参：e 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {col.name: getattr(e, col.name) for col in Episode.__table__.columns}


def episode_asset_usage_items(
    db: Session,
    *,
    model,
    ids: list[str],
    usage_items: list,
) -> list[dict]:
    """业务函数：处理 episode_asset_usage_items 对应的业务流程、校验或数据转换。

    入参：db、model、ids、usage_items 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    usage_by_id = {
        str(item.get("id")): item
        for item in usage_items
        if isinstance(item, dict) and item.get("id")
    }
    rows = db.query(model).filter(model.id.in_(ids)).all() if ids else []
    names = {row.id: row.name for row in rows}
    result = []
    for asset_id in ids:
        item = dict(usage_by_id.get(asset_id) or {})
        item["id"] = asset_id
        item.setdefault("name", names.get(asset_id, asset_id))
        item.setdefault("source", "existing")
        if not item.get("usage"):
            item["usage"] = "本集剧情资产。"
        result.append(item)
    return result


def episode_asset_scope_payload(db: Session, episode: Episode) -> dict:
    """业务函数：处理 episode_asset_scope_payload 对应的业务流程、校验或数据转换。

    入参：db、episode 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    service = AITextArtifactService(db)
    artifact = service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
    )
    content = artifact.content_json if artifact and isinstance(artifact.content_json, dict) else {}
    script = episode.script_json if isinstance(episode.script_json, dict) else {}
    script_scope = script.get("episode_asset_scope") if isinstance(script.get("episode_asset_scope"), dict) else {}
    character_ids = list(dict.fromkeys(str(item) for item in (content.get("character_ids") or script_scope.get("character_ids") or []) if item))
    scene_ids = list(dict.fromkeys(str(item) for item in (content.get("scene_ids") or script_scope.get("scene_ids") or []) if item))
    asset_usage = content.get("asset_usage") if isinstance(content.get("asset_usage"), dict) else {}
    generated_assets = content.get("generated_assets") if isinstance(content.get("generated_assets"), dict) else {"characters": [], "scenes": []}
    return {
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "characters": episode_asset_usage_items(
            db,
            model=Character,
            ids=character_ids,
            usage_items=asset_usage.get("characters") if isinstance(asset_usage.get("characters"), list) else [],
        ),
        "scenes": episode_asset_usage_items(
            db,
            model=Scene,
            ids=scene_ids,
            usage_items=asset_usage.get("scenes") if isinstance(asset_usage.get("scenes"), list) else [],
        ),
        "generated_assets": generated_assets,
        "source": "episode_outline" if artifact else script_scope.get("source", "missing"),
    }


def active_video_runs_by_episode(db: Session, series_id: str) -> dict[str, VideoProductionRun]:
    """业务函数：处理 active_video_runs_by_episode 对应的业务流程、校验或数据转换。

    入参：db、series_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    runs = db.query(VideoProductionRun).filter(
        VideoProductionRun.series_id == series_id
    ).order_by(VideoProductionRun.created_at.desc()).all()
    active_runs: dict[str, VideoProductionRun] = {}
    for run in runs:
        if run.episode_id in active_runs:
            continue
        if run.status not in VIDEO_RUN_TERMINAL_STATUSES:
            active_runs[run.episode_id] = run
    return active_runs


def episode_dict_with_video_run(e: Episode, active_run: VideoProductionRun | None = None) -> dict:
    """业务函数：处理 episode_dict_with_video_run 对应的业务流程、校验或数据转换。

    入参：e、active_run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    payload = episode_dict(e)
    if active_run:
        payload["active_video_run_id"] = active_run.id
        payload["video_run_status"] = active_run.status
        payload["video_run_stage"] = active_run.current_stage
        payload["video_run_route"] = f"/video-production/{active_run.id}"
    return payload


def character_reference_urls(c: Character) -> list[str]:
    """业务函数：处理 character_reference_urls 对应的业务流程、校验或数据转换。

    入参：c 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return [u for u in [
        c.avatar_front_url,
        c.avatar_side_url,
        c.avatar_threequarter_url,
        c.avatar_fullbody_url,
    ] if reference_url_is_usable(u)]


def scene_reference_urls(s: Scene) -> list[str]:
    """业务函数：处理 scene_reference_urls 对应的业务流程、校验或数据转换。

    入参：s 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return [u for u in [
        s.reference_wideshot_url,
        s.reference_midshot_url,
        s.reference_aerial_url,
    ] if reference_url_is_usable(u)]


def reference_status(series: Series) -> dict:
    """业务函数：处理 reference_status 对应的业务流程、校验或数据转换。

    入参：series 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    characters = list(series.characters or [])
    scenes = list(series.scenes or [])
    return {
        "characters": {
            "total": len(characters),
            "ready": sum(1 for c in characters if character_reference_urls(c)),
        },
        "scenes": {
            "total": len(scenes),
            "ready": sum(1 for s in scenes if scene_reference_urls(s)),
        },
    }


def agency_console_payload(db: Session, series: Series, series_id: str) -> dict:
    """业务函数：处理 agency_console_payload 对应的业务流程、校验或数据转换。

    入参：db、series、series_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    episodes = db.query(Episode).filter(
        Episode.series_id == series_id
    ).order_by(Episode.episode_number).all()
    latest_pipeline_run = db.query(PipelineRun).filter(
        PipelineRun.series_id == series_id
    ).order_by(PipelineRun.created_at.desc()).first()
    latest_video_run = db.query(VideoProductionRun).filter(
        VideoProductionRun.series_id == series_id
    ).order_by(VideoProductionRun.created_at.desc()).first()

    candidates = [
        ("pipeline", latest_pipeline_run),
        ("video_production", latest_video_run),
    ]
    run_type, latest_run = max(
        ((run_type, run) for run_type, run in candidates if run),
        key=lambda item: (item[1].created_at, 1 if item[0] == "video_production" else 0),
        default=(None, None),
    )
    generated_video = None
    if latest_run:
        generated_video = db.query(GeneratedVideo).filter(
            GeneratedVideo.pixelle_task_id == latest_run.id
        ).first()
    return build_agency_console_payload(series, episodes, latest_run, generated_video, run_type)
