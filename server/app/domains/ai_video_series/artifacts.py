"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 artifacts 相关业务规则、状态转换和外部系统边界。
"""

from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.ai_video_series import Episode, Series
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService


PLACEHOLDER_STORY_PLAN_SOURCES = {"system_backfill", "legacy_run_backfill"}


def actor_id(user) -> str | None:
    """业务函数：处理 actor_id 对应的业务流程、校验或数据转换。

    入参：user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if isinstance(user, tuple) and user:
        return str(user[0])
    if isinstance(user, str):
        return user
    return None


def storyboard_text_values(storyboard: dict, key: str) -> list[str]:
    """业务函数：处理 storyboard_text_values 对应的业务流程、校验或数据转换。

    入参：storyboard、key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    frames = storyboard.get("frames") or []
    if not isinstance(frames, list):
        return []
    values: list[str] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        if key == "dialogue":
            for line_key in ("dialogue", "narration", "voiceover"):
                value = frame.get(line_key)
                if isinstance(value, str) and value:
                    values.append(value)
                elif isinstance(value, list):
                    values.extend(str(item) for item in value if item)
            continue
        value = frame.get(key)
        if value:
            values.append(str(value))
    return values


def record_episode_update_text_artifacts(db: Session, episode: Episode, payload: dict, user) -> None:
    """业务函数：处理 record_episode_update_text_artifacts 对应的业务流程、校验或数据转换。

    入参：db、episode、payload、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    service = AITextArtifactService(db)
    actor = actor_id(user) or "episode_update"
    base_input = {
        "source": "series_update_episode",
        "updated_fields": sorted(payload.keys()),
    }
    if isinstance(payload.get("script_json"), dict):
        script_json = payload["script_json"]
        artifact = service.create_artifact(
            series_id=episode.series_id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_script",
            source_type="human_edit",
            input_json=base_input,
            content_json=script_json,
            content_text=json.dumps(script_json, ensure_ascii=False),
            model_trace_json={"source": "series_update_episode", "stage": "manual_script_update"},
            created_by=actor,
            commit=False,
        )
        service.approve_artifact(artifact.id, actor_user_id=actor, commit=False)
    if isinstance(payload.get("storyboard_json"), dict):
        storyboard_json = payload["storyboard_json"]
        dialogue_lines = storyboard_text_values(storyboard_json, "dialogue")
        image_prompts = storyboard_text_values(storyboard_json, "image_prompt")
        video_prompts = storyboard_text_values(storyboard_json, "video_prompt")
        specs = [
            ("storyboard", storyboard_json, "\n".join(dialogue_lines)),
            ("dialogue", {"lines": dialogue_lines}, "\n".join(dialogue_lines)),
            ("image_prompt", {"prompts": image_prompts}, "\n".join(image_prompts)),
        ]
        if video_prompts:
            specs.append(("video_prompt", {"prompts": video_prompts}, "\n".join(video_prompts)))
        for artifact_type, content_json, content_text in specs:
            artifact = service.create_artifact(
                series_id=episode.series_id,
                episode_id=episode.id,
                target_type="episode",
                target_id=episode.id,
                artifact_type=artifact_type,
                source_type="human_edit",
                input_json=base_input,
                content_json=content_json,
                content_text=content_text,
                model_trace_json={"source": "series_update_episode", "stage": "manual_storyboard_update"},
                created_by=actor,
                commit=False,
            )
            service.approve_artifact(artifact.id, actor_user_id=actor, commit=False)


def story_plan_artifact_summary(artifact) -> dict:
    """业务函数：处理 story_plan_artifact_summary 对应的业务流程、校验或数据转换。

    入参：artifact 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "id": artifact.id,
        "artifact_type": artifact.artifact_type,
        "target_type": artifact.target_type,
        "target_id": artifact.target_id,
        "episode_id": artifact.episode_id,
        "version": artifact.version,
        "status": artifact.status,
        "source_type": artifact.source_type,
    }


def completed_story_plan_payload(db: Session, series: Series) -> dict | None:
    """业务函数：处理 completed_story_plan_payload 对应的业务流程、校验或数据转换。

    入参：db、series 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    target_episode_count = max(1, int(series.total_episodes or 1))
    episodes = (
        db.query(Episode)
        .filter(Episode.series_id == series.id, Episode.episode_number <= target_episode_count)
        .order_by(Episode.episode_number)
        .all()
    )
    if len(episodes) < target_episode_count:
        return None

    service = AITextArtifactService(db)
    artifacts = []
    for artifact_type in ("series_story_plan", "season_arc", "continuity_ledger"):
        artifact = service.latest_approved(
            target_type="series",
            target_id=series.id,
            artifact_type=artifact_type,
        )
        if not artifact:
            return None
        artifacts.append(story_plan_artifact_summary(artifact))
    for episode in episodes:
        artifact = service.latest_approved(
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
        )
        if not artifact:
            return None
        if artifact.source_type in PLACEHOLDER_STORY_PLAN_SOURCES:
            return None
        summary = story_plan_artifact_summary(artifact)
        summary["episode_number"] = int(episode.episode_number)
        artifacts.append(summary)

    current = dict((series.story_bible_json or {}).get("story_planning") or {})
    status = str(current.get("status") or "").lower()
    if status not in {"completed", "fallback"}:
        current = _mark_story_planning_completed(
            db,
            series,
            current,
            artifacts=artifacts,
            target_episode_count=target_episode_count,
        )
        status = "completed"
    return {
        "ok": True,
        "status": status,
        "series_id": series.id,
        "job_id": current.get("job_id"),
        "story_planning": current,
        "artifacts": artifacts,
    }


def _mark_story_planning_completed(
    db: Session,
    series: Series,
    current: dict,
    *,
    artifacts: list[dict],
    target_episode_count: int,
) -> dict:
    """业务函数：处理 _mark_story_planning_completed 对应的业务流程、校验或数据转换。

    入参：db、series、current、artifacts、target_episode_count 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    story_bible = dict(series.story_bible_json or {})
    current = dict(current)
    current["version"] = int(current.get("version") or 1)
    current["status"] = "completed"
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    current.pop("error", None)
    current["result"] = {"artifacts": artifacts, "target_episode_count": target_episode_count}
    current["completed_at"] = datetime.now(timezone.utc).isoformat()
    story_bible["story_planning"] = current
    series.story_bible_json = story_bible
    flag_modified(series, "story_bible_json")
    db.commit()
    db.refresh(series)
    return current
