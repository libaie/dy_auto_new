"""系列 + 剧集管理 API."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from app.database import SessionLocal, get_db
from app.deps import require_role, verify_admin_token
from sqlalchemy.exc import IntegrityError
from app.config import bj_now
from app.db_models import Series, Episode, Character, Scene, PipelineRun, GeneratedVideo, ProductionJob, ProductionPlan, VideoProductionRun, series_characters, series_scenes
from app.services.ai_generator import ai_generator
from app.services.video_agency_team import (
    build_video_agency_team,
    ensure_video_agency_team,
    summarize_video_agency_team,
)
from app.services.agency_console import build_agency_console_payload
from app.services.agency_orchestrator import AgencyOrchestrator
from app.services.ai_text_artifact_service import AITextArtifactService
from app.services.asset_lifecycle_service import (
    AssetLifecycleError,
    delete_or_archive_series,
    unlink_character_from_series,
    unlink_scene_from_series,
)
from app.services.reference_asset_service import (
    ReferenceAssetError,
    SCENE_EMPTY_PLATE_INSTRUCTION,
    generate_reference_url,
    reference_url_is_usable,
)
from app.services.production_queue_service import claim_next_job, fail_job, mark_job_completed
from app.services.production_status import JOB_LEASED, JOB_QUEUED, JOB_RETRY_WAIT, JOB_RUNNING, PLAN_COMPLETED, PLAN_READY
from app.services.production_run_service import generate_episode_script_storyboard
from app.services.runtime_model_config import RuntimeModelConfigError, resolve_runtime_model_config
from app.services.series_planning_service import ensure_episode_placeholders, ensure_series_continuity_artifacts, generate_series_story_plan
from app.services.visual_style_inference_service import (
    append_visual_style_constraints,
    infer_visual_style_from_story,
    merge_visual_style,
    reference_prompt_matches_visual_style,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/series", tags=["series"])


class SeriesCreate(BaseModel):
    title: str
    logline: Optional[str] = None
    genre: str = "drama"
    total_episodes: int = 30
    target_duration: int = 90
    mode: str = "step_by_step"
    pilot_first: bool = True


class SeriesUpdate(BaseModel):
    title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    total_episodes: Optional[int] = None
    target_duration: Optional[int] = None
    mode: Optional[str] = None
    pilot_first: Optional[bool] = None


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_json: Optional[dict] = None
    storyboard_json: Optional[dict] = None


class StyleLockResponse(BaseModel):
    ok: bool
    status: Optional[str] = None
    story_bible: dict = Field(default_factory=dict)
    missing_assets: list[dict] = Field(default_factory=list)
    audit_reports: list[dict] = Field(default_factory=list)


class StyleLockWorkerStepRequest(BaseModel):
    lease_id: str = "style-lock-worker"
    batch_size: int = Field(default=1, ge=1, le=20)


class StoryPlanWorkerStepRequest(BaseModel):
    lease_id: str = "story-plan-worker"
    batch_size: int = Field(default=1, ge=1, le=20)


class EpisodeScriptGenerationRequest(BaseModel):
    target_duration_seconds: int | None = Field(default=None, ge=1)


def _missing_agency_trace(stage: str, exc: Exception) -> dict:
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "EXPERT_MODEL_CONFIG_MISSING",
        "error_message": str(exc),
    }


def _timeout_agency_trace(stage: str, timeout_seconds: float) -> dict:
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "STYLE_LOCK_REVIEW_TIMEOUT",
        "error_message": f"Style lock expert review exceeded {timeout_seconds:g} seconds.",
    }


def _agency_trace_blocks(trace: dict | None) -> bool:
    return bool(isinstance(trace, dict) and trace.get("stage_status") in {"blocked", "failed"})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _style_lock_status(lock: dict | None) -> str:
    if not isinstance(lock, dict):
        return "unlocked"
    if lock.get("status"):
        return str(lock["status"])
    return "locked" if lock.get("locked") else "unlocked"


def _upsert_reference_progress_item(series: Series, item: dict) -> None:
    story_bible = dict(series.story_bible_json or {})
    lock = dict(story_bible.get("style_lock") or {})
    progress = list(lock.get("reference_progress") or [])
    key = (item.get("asset_type"), item.get("asset_id"), item.get("slot"))
    index = next((
        idx for idx, current in enumerate(progress)
        if (current.get("asset_type"), current.get("asset_id"), current.get("slot")) == key
    ), None)
    payload = {**item, "updated_at": _utc_now_iso()}
    if index is None:
        progress.append(payload)
    else:
        progress[index] = {**progress[index], **payload}
    lock["reference_progress"] = progress
    story_bible["style_lock"] = lock
    series.story_bible_json = story_bible
    flag_modified(series, "story_bible_json")


def _record_reference_slot_progress(
    db: Session,
    series: Series,
    row,
    *,
    asset_type: str,
    slot: str,
    label: str,
    status: str,
    prompt: str = "",
    url: str | None = None,
    error: str | None = None,
) -> None:
    meta_json = dict(row.meta_json or {})
    reference_generation = dict(meta_json.get("reference_generation") or {})
    reference_generation[slot] = {
        **(reference_generation.get(slot) or {}),
        "status": status,
        "source": "style_lock",
        "label": label,
        "prompt": prompt,
        "url": url or getattr(row, slot, None),
        "error": error,
        "updated_at": _utc_now_iso(),
    }
    meta_json["reference_generation"] = reference_generation
    row.meta_json = meta_json
    flag_modified(row, "meta_json")
    _upsert_reference_progress_item(series, {
        "asset_type": asset_type,
        "asset_id": row.id,
        "asset_name": getattr(row, "name", ""),
        "slot": slot,
        "label": label,
        "status": status,
        "url": url or getattr(row, slot, None),
        "error": error,
    })
    db.commit()


def _stored_reference_prompt_matches(row, slot: str, visual_style: dict) -> bool:
    meta_json = row.meta_json or {}
    reference_generation = meta_json.get("reference_generation") if isinstance(meta_json, dict) else {}
    slot_meta = reference_generation.get(slot) if isinstance(reference_generation, dict) else {}
    stored_prompt = slot_meta.get("prompt") if isinstance(slot_meta, dict) else None
    return reference_prompt_matches_visual_style(stored_prompt, visual_style)


def _set_style_lock_state(
    db: Session,
    series: Series,
    *,
    status: str,
    version: int | None = None,
    locked: bool | None = None,
    error: str | None = None,
) -> dict:
    story_bible = dict(series.story_bible_json or {})
    current = dict(story_bible.get("style_lock") or {})
    current["status"] = status
    if version is not None:
        current["version"] = version
    if locked is not None:
        current["locked"] = locked
    current["series_id"] = series.id
    if status == "locking":
        current["lock_started_at"] = _utc_now_iso()
        current["lock_completed_at"] = None
        current["lock_error"] = None
        current["missing_assets"] = []
        current["reference_progress"] = []
        current.pop("agency_trace", None)
    elif status in {"locked", "blocked", "failed"}:
        current["lock_completed_at"] = _utc_now_iso()
        current["lock_error"] = error
    story_bible["style_lock"] = current
    series.story_bible_json = story_bible
    flag_modified(series, "story_bible_json")
    db.commit()
    db.refresh(series)
    return current


def _record_style_lock_series_bible_artifact(
    db: Session,
    series: Series,
    story_bible: dict,
    *,
    missing_assets: list[dict],
) -> None:
    style_lock = story_bible.get("style_lock") if isinstance(story_bible, dict) else {}
    if not isinstance(style_lock, dict):
        return
    service = AITextArtifactService(db)
    artifact = service.create_artifact(
        series_id=series.id,
        target_type="series",
        target_id=series.id,
        artifact_type="series_bible",
        source_type="ai",
        input_json={
            "source": "style_lock",
            "series": {"title": series.title, "logline": series.logline, "genre": series.genre},
            "style_lock_version": style_lock.get("version", 0),
        },
        content_json=story_bible,
        content_text=series.logline or series.title,
        model_trace_json={
            "source": "style_lock",
            "stage": "style_lock",
            "status": style_lock.get("status"),
            "missing_asset_count": len(missing_assets),
        },
        review_trace_json=style_lock.get("agency_trace") if isinstance(style_lock.get("agency_trace"), dict) else {},
        created_by="style_lock",
        commit=False,
    )
    if style_lock.get("locked"):
        service.approve_artifact(artifact.id, actor_user_id="style_lock", commit=False)


def _actor_id(user) -> str | None:
    if isinstance(user, tuple) and user:
        return str(user[0])
    if isinstance(user, str):
        return user
    return None


def _storyboard_text_values(storyboard: dict, key: str) -> list[str]:
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


def _record_episode_update_text_artifacts(db: Session, episode: Episode, payload: dict, user) -> None:
    service = AITextArtifactService(db)
    actor = _actor_id(user) or "episode_update"
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
        dialogue_lines = _storyboard_text_values(storyboard_json, "dialogue")
        image_prompts = _storyboard_text_values(storyboard_json, "image_prompt")
        video_prompts = _storyboard_text_values(storyboard_json, "video_prompt")
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


STYLE_LOCK_STAGE = "style_lock"
STYLE_LOCK_ACTIVE_JOB_STATUSES = (JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT)
STYLE_LOCK_JOB_LEASE_SECONDS = 3600
STORY_PLANNING_STAGE = "story_planning"
STORY_PLANNING_ACTIVE_JOB_STATUSES = (JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT)
STORY_PLANNING_JOB_LEASE_SECONDS = 3600
STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS", "30"))
AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_ASSET_MODEL_TIMEOUT_SECONDS", "180"))


def _style_lock_in_progress_error() -> HTTPException:
    return HTTPException(409, {
        "code": "STYLE_LOCK_IN_PROGRESS",
        "message": "Style lock is already running for this series.",
    })


def _story_planning_in_progress_error() -> HTTPException:
    return HTTPException(409, {
        "code": "STORY_PLANNING_IN_PROGRESS",
        "message": "Story planning is already running for this series.",
    })


def _active_style_lock_job(db: Session, series_id: str) -> ProductionJob | None:
    return (
        db.query(ProductionJob)
        .filter(ProductionJob.target_type == "series")
        .filter(ProductionJob.target_id == series_id)
        .filter(ProductionJob.stage == STYLE_LOCK_STAGE)
        .filter(ProductionJob.status.in_(STYLE_LOCK_ACTIVE_JOB_STATUSES))
        .order_by(ProductionJob.created_at.desc())
        .first()
    )


def _active_story_plan_job(db: Session, series_id: str) -> ProductionJob | None:
    return (
        db.query(ProductionJob)
        .filter(ProductionJob.target_type == "series")
        .filter(ProductionJob.target_id == series_id)
        .filter(ProductionJob.stage == STORY_PLANNING_STAGE)
        .filter(ProductionJob.status.in_(STORY_PLANNING_ACTIVE_JOB_STATUSES))
        .order_by(ProductionJob.created_at.desc())
        .first()
    )


def _enqueue_style_lock_job(db: Session, series: Series, version: int) -> ProductionJob:
    if _active_style_lock_job(db, series.id):
        raise _style_lock_in_progress_error()

    plan = ProductionPlan(
        series_id=series.id,
        status=PLAN_READY,
        active_version=1,
        target_total_duration_seconds=0,
    )
    db.add(plan)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="series",
        target_id=series.id,
        stage=STYLE_LOCK_STAGE,
        status=JOB_QUEUED,
        idempotency_key=f"style_lock:{series.id}:v{version}",
        priority=10,
        scheduled_at=bj_now(),
        max_attempts=3,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProductionJob).filter(
            ProductionJob.idempotency_key == f"style_lock:{series.id}:v{version}"
        ).first()
        if existing and existing.status in STYLE_LOCK_ACTIVE_JOB_STATUSES:
            raise _style_lock_in_progress_error()
        raise
    db.refresh(job)
    return job


def _set_story_planning_state(
    db: Session,
    series: Series,
    *,
    status: str,
    version: int | None = None,
    job_id: str | None = None,
    error: str | None = None,
    result: dict | None = None,
) -> dict:
    story_bible = dict(series.story_bible_json or {})
    current = dict(story_bible.get("story_planning") or {})
    if version is not None:
        current["version"] = version
    elif "version" not in current:
        current["version"] = 1
    current["status"] = status
    current["updated_at"] = _utc_now_iso()
    if job_id is not None:
        current["job_id"] = job_id
    if error is not None:
        current["error"] = error
    elif status in {"queued", "running", "completed", "fallback"}:
        current.pop("error", None)
    if result is not None:
        current["result"] = result
    if status in {"completed", "fallback", "failed"}:
        current["completed_at"] = _utc_now_iso()
    story_bible["story_planning"] = current
    series.story_bible_json = story_bible
    flag_modified(series, "story_bible_json")
    db.commit()
    db.refresh(series)
    return current


def _enqueue_story_plan_job(db: Session, series: Series, version: int) -> ProductionJob:
    if _active_story_plan_job(db, series.id):
        raise _story_planning_in_progress_error()

    plan = ProductionPlan(
        series_id=series.id,
        status=PLAN_READY,
        active_version=1,
        target_total_duration_seconds=0,
    )
    db.add(plan)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="series",
        target_id=series.id,
        stage=STORY_PLANNING_STAGE,
        status=JOB_QUEUED,
        idempotency_key=f"story_planning:{series.id}:v{version}",
        priority=10,
        scheduled_at=bj_now(),
        max_attempts=3,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProductionJob).filter(
            ProductionJob.idempotency_key == f"story_planning:{series.id}:v{version}"
        ).first()
        if existing and existing.status in STORY_PLANNING_ACTIVE_JOB_STATUSES:
            raise _story_planning_in_progress_error()
        raise
    db.refresh(job)
    return job


def _story_plan_artifact_summary(artifact) -> dict:
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


def _completed_story_plan_payload(db: Session, series: Series) -> dict | None:
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
        artifacts.append(_story_plan_artifact_summary(artifact))
    for episode in episodes:
        artifact = service.latest_approved(
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
        )
        if not artifact:
            return None
        if artifact.source_type in _PLACEHOLDER_STORY_PLAN_SOURCES:
            return None
        summary = _story_plan_artifact_summary(artifact)
        summary["episode_number"] = int(episode.episode_number)
        artifacts.append(summary)

    current = dict((series.story_bible_json or {}).get("story_planning") or {})
    status = str(current.get("status") or "").lower()
    if status not in {"completed", "fallback"}:
        current = _set_story_planning_state(
            db,
            series,
            status="completed",
            version=int(current.get("version") or 1),
            result={"artifacts": artifacts, "target_episode_count": target_episode_count},
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


# === AI 自动生成角色 + 场景 ===

@router.post("/{series_id}/auto-generate")
async def auto_generate_series_assets(series_id: str, db: Session = Depends(get_db),
                                      user = Depends(verify_admin_token)):
    """根据系列 logline 自动生成角色和场景，自动创建并关联到系列。"""
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    if not s.logline:
        raise HTTPException(400, "请先填写系列的故事概要 (logline)")

    text = s.logline
    genre = s.genre

    # 1. 生成角色
    char_prompt = f"""故事概要：{text}
类型：{genre}
需要生成的角色数量：4

为每个角色生成以下字段的 JSON：
- name: 角色姓名
- role_type: protagonist(主角) / antagonist(反派) / supporting(配角) / cameo(客串)
- gender: male / female
- age_range: 年龄段，如 "25-30"
- personality: 性格描述（2-3句）
- appearance_desc: 详细外貌描述（50-100字，用于 AI 图像生成）
- outfit_desc: 典型着装描述（30-50字，用于 AI 图像生成）

严格输出 JSON 数组，格式：{{"characters": [...]}}"""
    try:
        raw_chars = await ai_generator.generate_custom(
            db,
            _CHAR_SYSTEM,
            char_prompt,
            max_tokens=4096,
            temperature=0.8,
            request_timeout_seconds=AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS,
        )
        char_data = _parse_json_with_key(raw_chars, "characters")
    except Exception as e:
        logger.warning("Auto-generate characters failed: %s", e)
        raise HTTPException(500, f"角色生成失败: {e}")

    # 2. 生成场景
    scene_prompt = f"""故事概要：{text}
类型：{genre}
需要生成的场景数量：5

为每个场景生成以下字段的 JSON：
- name: 场景/地点名称
- scene_type: indoor(室内) / outdoor(室外) / transition(转场) / special(特殊)
- location_desc: 详细地点描述（50-100字，用于 AI 图像生成）
- lighting: day(白天) / dusk(黄昏) / night(夜晚) / warm_indoor(室内暖光) / cold_fluorescent(冷荧光)
- mood: warm(温馨) / tense(紧张) / romantic(浪漫) / mysterious(悬疑) / sad(悲伤) / joyful(欢快)

严格输出 JSON 数组，格式：{{"scenes": [...]}}"""
    try:
        raw_scenes = await ai_generator.generate_custom(
            db,
            _SCENE_SYSTEM,
            scene_prompt,
            max_tokens=4096,
            temperature=0.8,
            request_timeout_seconds=AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS,
        )
        scene_data = _parse_json_with_key(raw_scenes, "scenes")
    except Exception as e:
        logger.warning("Auto-generate scenes failed: %s", e)
        raise HTTPException(500, f"场景生成失败: {e}")

    # 3. 持久化角色
    created_chars = []
    for c in char_data["characters"]:
        ch = Character(
            name=c.get("name", "?"),
            role_type=c.get("role_type", "supporting"),
            gender=c.get("gender", "male"),
            age_range=c.get("age_range", ""),
            personality=c.get("personality", ""),
            appearance_desc=c.get("appearance_desc", ""),
            outfit_desc=c.get("outfit_desc", ""),
        )
        db.add(ch)
        created_chars.append(ch)

    # 4. 持久化场景
    created_scenes = []
    for sc in scene_data["scenes"]:
        scene = Scene(
            name=sc.get("name", "?"),
            scene_type=sc.get("scene_type", "indoor"),
            location_desc=sc.get("location_desc", ""),
            lighting=sc.get("lighting", ""),
            mood=sc.get("mood", ""),
        )
        db.add(scene)
        created_scenes.append(scene)

    db.flush()

    # 5. 关联到系列
    for ch in created_chars:
        s.characters.append(ch)
    for sc in created_scenes:
        s.scenes.append(sc)

    db.commit()

    return {
        "ok": True,
        "characters": [_series_char_dict(c) for c in created_chars],
        "scenes": [_series_scene_dict(sc) for sc in created_scenes],
    }


_CHAR_SYSTEM = """你是一位资深的编剧和角色设计师。根据故事概要生成详细的角色档案。
输出必须是合法的 JSON，不要包含 markdown 代码块标记。每个角色包含所有要求字段。
appearance_desc 要足够详细（50-100字），用于 AI 图像生成。角色之间要有区分度。"""

_SCENE_SYSTEM = """你是一位资深的电影导演和场景设计师。根据故事概要生成详细的场景描述。
输出必须是合法的 JSON，不要包含 markdown 代码块标记。每个场景包含所有要求字段。
location_desc 要足够详细（50-100字），用于 AI 图像生成。场景之间要有区分度。"""


def _parse_json_with_key(raw: str, key: str) -> dict:
    import re
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Brace-counting extraction: find {"key":[...]} with proper nesting
    key_pos = raw.find('"' + key + '"')
    if key_pos >= 0:
        # Find the opening brace before the key
        brace_start = raw.rfind('{', 0, key_pos)
        if brace_start >= 0:
            depth = 0
            i = brace_start
            while i < len(raw):
                if raw[i] == '{':
                    depth += 1
                elif raw[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[brace_start:i + 1])
                        except json.JSONDecodeError:
                            pass
                        break
                i += 1
    raise ValueError(f"无法解析 LLM 返回的 JSON (key={key}): {raw[:300]}")


def _series_char_dict(c: Character) -> dict:
    return {col.name: getattr(c, col.name) for col in Character.__table__.columns}


def _series_scene_dict(s: Scene) -> dict:
    return {col.name: getattr(s, col.name) for col in Scene.__table__.columns}


def _series_dict(s: Series, include_linked_assets: bool = False) -> dict:
    base = {col.name: getattr(s, col.name) for col in Series.__table__.columns}
    base["character_count"] = len(s.characters) if hasattr(s, "characters") else 0
    base["scene_count"] = len(s.scenes) if hasattr(s, "scenes") else 0
    if include_linked_assets:
        base["characters"] = [_series_char_dict(c) for c in (s.characters or [])]
        base["scenes"] = [_series_scene_dict(scene) for scene in (s.scenes or [])]
    return base


def _episode_dict(e: Episode) -> dict:
    return {col.name: getattr(e, col.name) for col in Episode.__table__.columns}


def _episode_asset_usage_items(
    db: Session,
    *,
    model,
    ids: list[str],
    usage_items: list,
) -> list[dict]:
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


def _episode_asset_scope_payload(db: Session, episode: Episode) -> dict:
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
        "characters": _episode_asset_usage_items(
            db,
            model=Character,
            ids=character_ids,
            usage_items=asset_usage.get("characters") if isinstance(asset_usage.get("characters"), list) else [],
        ),
        "scenes": _episode_asset_usage_items(
            db,
            model=Scene,
            ids=scene_ids,
            usage_items=asset_usage.get("scenes") if isinstance(asset_usage.get("scenes"), list) else [],
        ),
        "generated_assets": generated_assets,
        "source": "episode_outline" if artifact else script_scope.get("source", "missing"),
    }


_VIDEO_RUN_TERMINAL_STATUSES = {"completed", "done", "failed", "cancelled", "canceled"}
_PLACEHOLDER_STORY_PLAN_SOURCES = {"system_backfill", "legacy_run_backfill"}


def _active_video_runs_by_episode(db: Session, series_id: str) -> dict[str, VideoProductionRun]:
    runs = db.query(VideoProductionRun).filter(
        VideoProductionRun.series_id == series_id
    ).order_by(VideoProductionRun.created_at.desc()).all()
    active_runs: dict[str, VideoProductionRun] = {}
    for run in runs:
        if run.episode_id in active_runs:
            continue
        if run.status not in _VIDEO_RUN_TERMINAL_STATUSES:
            active_runs[run.episode_id] = run
    return active_runs


def _episode_dict_with_video_run(e: Episode, active_run: VideoProductionRun | None = None) -> dict:
    payload = _episode_dict(e)
    if active_run:
        payload["active_video_run_id"] = active_run.id
        payload["video_run_status"] = active_run.status
        payload["video_run_stage"] = active_run.current_stage
        payload["video_run_route"] = f"/video-production/{active_run.id}"
    return payload


def _character_reference_urls(c: Character) -> list[str]:
    return [u for u in [
        c.avatar_front_url,
        c.avatar_side_url,
        c.avatar_threequarter_url,
        c.avatar_fullbody_url,
    ] if reference_url_is_usable(u)]


def _scene_reference_urls(s: Scene) -> list[str]:
    return [u for u in [
        s.reference_wideshot_url,
        s.reference_midshot_url,
        s.reference_aerial_url,
    ] if reference_url_is_usable(u)]


_CHARACTER_REFERENCE_SLOTS = (
    ("avatar_front_url", "front-view character anchor sheet"),
    ("avatar_threequarter_url", "three-quarter character anchor sheet"),
    ("avatar_side_url", "side-profile character anchor sheet"),
    ("avatar_fullbody_url", "full-body costume and proportions anchor sheet"),
)

_SCENE_REFERENCE_SLOTS = (
    ("reference_wideshot_url", "wide establishing scene reference"),
    ("reference_midshot_url", "mid-shot scene lighting reference"),
    ("reference_aerial_url", "high-angle environment layout reference"),
)
STYLE_LOCK_REFERENCE_CONCURRENCY = 4


def _reference_status(series: Series) -> dict:
    characters = list(series.characters or [])
    scenes = list(series.scenes or [])
    return {
        "characters": {
            "total": len(characters),
            "ready": sum(1 for c in characters if _character_reference_urls(c)),
        },
        "scenes": {
            "total": len(scenes),
            "ready": sum(1 for s in scenes if _scene_reference_urls(s)),
        },
    }


async def _generate_reference_image(
    db: Session,
    prompt: str,
    *,
    destination_context: dict | None = None,
) -> str | None:
    try:
        return await generate_reference_url(
            db,
            prompt,
            destination_context=destination_context,
        )
    except ReferenceAssetError as e:
        logger.warning("Reference image generation failed: %s", e.message)
    except Exception as e:
        logger.warning("Reference image generation failed: %s", e)
        return None


async def _generate_reference_image_isolated(
    db: Session,
    prompt: str,
    *,
    destination_context: dict,
    semaphore: asyncio.Semaphore,
) -> str | None:
    SessionFactory = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)
    async with semaphore:
        generation_db = SessionFactory()
        try:
            return await _generate_reference_image(
                generation_db,
                prompt,
                destination_context=destination_context,
            )
        finally:
            generation_db.close()


async def _ensure_series_assets(series: Series, db: Session) -> tuple[list[Character], list[Scene]]:
    created_chars: list[Character] = []
    created_scenes: list[Scene] = []

    if not series.characters:
        if not series.logline:
            raise HTTPException(400, "Series logline is required before style lock")
        raw_chars = await ai_generator.generate_custom(
            db,
            _CHAR_SYSTEM,
            f"Story logline: {series.logline}\nGenre: {series.genre}\nReturn 3-5 characters as JSON with key characters.",
            max_tokens=4096,
            temperature=0.8,
        )
        char_data = _parse_json_with_key(raw_chars, "characters")
        for c in char_data["characters"]:
            ch = Character(
                name=c.get("name", "?"),
                role_type=c.get("role_type", "supporting"),
                gender=c.get("gender", "male"),
                age_range=c.get("age_range", ""),
                personality=c.get("personality", ""),
                appearance_desc=c.get("appearance_desc", ""),
                outfit_desc=c.get("outfit_desc", ""),
            )
            db.add(ch)
            created_chars.append(ch)

    if not series.scenes:
        if not series.logline:
            raise HTTPException(400, "Series logline is required before style lock")
        raw_scenes = await ai_generator.generate_custom(
            db,
            _SCENE_SYSTEM,
            f"Story logline: {series.logline}\nGenre: {series.genre}\nReturn 3-5 locations as JSON with key scenes.",
            max_tokens=4096,
            temperature=0.8,
        )
        scene_data = _parse_json_with_key(raw_scenes, "scenes")
        for sc in scene_data["scenes"]:
            scene = Scene(
                name=sc.get("name", "?"),
                scene_type=sc.get("scene_type", "indoor"),
                location_desc=sc.get("location_desc", ""),
                lighting=sc.get("lighting", ""),
                mood=sc.get("mood", ""),
            )
            db.add(scene)
            created_scenes.append(scene)

    if created_chars or created_scenes:
        db.flush()
        for ch in created_chars:
            series.characters.append(ch)
        for scene in created_scenes:
            series.scenes.append(scene)

    return created_chars, created_scenes


async def _fill_reference_assets(series: Series, db: Session) -> list[dict]:
    missing: list[dict] = []
    pending_jobs: list[dict] = []
    current_lock = (series.story_bible_json or {}).get("style_lock", {})
    style_lock_version = int(current_lock.get("version") or 1) if isinstance(current_lock, dict) else 1
    visual_style = infer_visual_style_from_story(
        series.title,
        series.logline,
        series.genre,
        series.story_bible_json or {},
        [character.appearance_desc for character in series.characters],
        [scene.location_desc for scene in series.scenes],
    )

    for character in series.characters:
        for field, angle_label in _CHARACTER_REFERENCE_SLOTS:
            prompt = f"{angle_label}, clear face, hairstyle, outfit, stable identity, consistent series style. "
            prompt += f"Name: {character.name}. Appearance: {character.appearance_desc or ''}. Outfit: {character.outfit_desc or ''}."
            prompt = append_visual_style_constraints(prompt, visual_style)
            if reference_url_is_usable(getattr(character, field)) and _stored_reference_prompt_matches(character, field, visual_style):
                _record_reference_slot_progress(
                    db,
                    series,
                    character,
                    asset_type="character",
                    slot=field,
                    label=angle_label,
                    status="ready",
                    url=getattr(character, field),
                )
                continue
            _record_reference_slot_progress(
                db,
                series,
                character,
                asset_type="character",
                slot=field,
                label=angle_label,
                status="generating",
                prompt=prompt,
            )
            pending_jobs.append({
                "row": character,
                "missing_type": "character_reference",
                "asset_type": "character",
                "slot": field,
                "label": angle_label,
                "prompt": prompt,
                "context": {
                    "series_id": series.id,
                    "style_lock_version": style_lock_version,
                    "asset_type": "character",
                    "asset_id": character.id,
                    "slot": field,
                },
            })

    for scene in series.scenes:
        for field, reference_label in _SCENE_REFERENCE_SLOTS:
            prompt = f"{reference_label}, consistent palette, lighting, environment design, and series style. "
            prompt += (
                f"Scene: {scene.name}. Location: {scene.location_desc or ''}. "
                f"Lighting: {scene.lighting or ''}. Mood: {scene.mood or ''}. "
                f"{SCENE_EMPTY_PLATE_INSTRUCTION}"
            )
            prompt = append_visual_style_constraints(prompt, visual_style)
            if reference_url_is_usable(getattr(scene, field)) and _stored_reference_prompt_matches(scene, field, visual_style):
                _record_reference_slot_progress(
                    db,
                    series,
                    scene,
                    asset_type="scene",
                    slot=field,
                    label=reference_label,
                    status="ready",
                    url=getattr(scene, field),
                )
                continue
            _record_reference_slot_progress(
                db,
                series,
                scene,
                asset_type="scene",
                slot=field,
                label=reference_label,
                status="generating",
                prompt=prompt,
            )
            pending_jobs.append({
                "row": scene,
                "missing_type": "scene_reference",
                "asset_type": "scene",
                "slot": field,
                "label": reference_label,
                "prompt": prompt,
                "context": {
                    "series_id": series.id,
                    "style_lock_version": style_lock_version,
                    "asset_type": "scene",
                    "asset_id": scene.id,
                    "slot": field,
                },
            })

    semaphore = asyncio.Semaphore(STYLE_LOCK_REFERENCE_CONCURRENCY)

    async def run_job(job: dict) -> tuple[dict, str | None]:
        url = await _generate_reference_image_isolated(
            db,
            job["prompt"],
            destination_context=job["context"],
            semaphore=semaphore,
        )
        return job, url

    tasks = [asyncio.create_task(run_job(job)) for job in pending_jobs]
    for completed in asyncio.as_completed(tasks):
        job, url = await completed
        row = job["row"]
        field = job["slot"]
        if url:
            setattr(row, field, url)
            _record_reference_slot_progress(
                db,
                series,
                row,
                asset_type=job["asset_type"],
                slot=field,
                label=job["label"],
                status="ready",
                prompt=job["prompt"],
                url=url,
            )
        else:
            missing.append({
                "type": job["missing_type"],
                "id": row.id,
                "name": row.name,
                "slot": field,
            })
            _record_reference_slot_progress(
                db,
                series,
                row,
                asset_type=job["asset_type"],
                slot=field,
                label=job["label"],
                status="failed",
                prompt=job["prompt"],
                error="Reference image generation failed",
            )

    return missing


def _build_story_bible(series: Series, version: int, missing_assets: list[dict]) -> dict:
    story_bible = dict(series.story_bible_json or {})
    current_lock = story_bible.get("style_lock", {})
    agency_team = ensure_video_agency_team(current_lock if isinstance(current_lock, dict) else {})
    reference_progress = current_lock.get("reference_progress", []) if isinstance(current_lock, dict) else []
    lock_started_at = current_lock.get("lock_started_at") if isinstance(current_lock, dict) else None
    inferred_visual_style = infer_visual_style_from_story(
        series.title,
        series.logline,
        series.genre,
        story_bible,
        [character.appearance_desc for character in series.characters],
        [scene.location_desc for scene in series.scenes],
    )
    visual_style = merge_visual_style(
        {
            "prompt": "consistent characters, stable locations, cinematic short-video framing",
            "aspect_ratio": "9:16",
            "color_policy": "keep the same palette and lighting mood across episodes",
        },
        inferred_visual_style,
    )
    story_bible["style_lock"] = {
        "locked": True,
        "status": "locked",
        "version": version,
        "series_id": series.id,
        "lock_started_at": lock_started_at,
        "agency_team": agency_team or build_video_agency_team(),
        "visual_style": visual_style,
        "audio_packaging": {
            "voice_policy": "use each character default_voice_id when available, otherwise project default TTS",
            "bgm_policy": "keep one restrained BGM bed per episode",
        },
        "edit_packaging": {
            "subtitle_style": "white subtitles with dark stroke, bottom safe area",
            "transition_style": "simple hard cuts or short dissolves",
            "intro_outro": "series title card and short ending CTA",
            "watermark": "",
        },
        "characters": [{
            "id": c.id,
            "name": c.name,
            "role_type": c.role_type,
            "appearance_desc": c.appearance_desc,
            "outfit_desc": c.outfit_desc,
            "default_voice_id": c.default_voice_id,
            "reference_urls": _character_reference_urls(c),
        } for c in series.characters],
        "scenes": [{
            "id": s.id,
            "name": s.name,
            "scene_type": s.scene_type,
            "location_desc": s.location_desc,
            "lighting": s.lighting,
            "mood": s.mood,
            "reference_urls": _scene_reference_urls(s),
        } for s in series.scenes],
        "missing_assets": missing_assets,
        "reference_progress": reference_progress,
    }
    return story_bible


# === Series CRUD ===

@router.get("")
def list_series(db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    all_series = db.query(Series).order_by(Series.updated_at.desc()).all()
    return {"ok": True, "series": [_series_dict(s) for s in all_series]}


@router.get("/{series_id}/style-lock")
def get_style_lock(series_id: str, db: Session = Depends(get_db),
                   _: str = Depends(verify_admin_token)):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    story_bible = dict(series.story_bible_json or {})
    lock = story_bible.get("style_lock", {})
    before_team = deepcopy(lock.get("agency_team")) if isinstance(lock, dict) else None
    agency_team = ensure_video_agency_team(lock if isinstance(lock, dict) else {})
    if isinstance(lock, dict) and lock.get("agency_team") != before_team:
        story_bible["style_lock"] = lock
        series.story_bible_json = story_bible
        flag_modified(series, "story_bible_json")
        db.commit()
        db.refresh(series)
        story_bible = dict(series.story_bible_json or story_bible)
        lock = story_bible.get("style_lock", {})
        agency_team = lock.get("agency_team", agency_team) if isinstance(lock, dict) else agency_team
    return {
        "ok": True,
        "locked": bool(lock.get("locked")) if isinstance(lock, dict) else False,
        "status": _style_lock_status(lock if isinstance(lock, dict) else None),
        "version": lock.get("version", 0) if isinstance(lock, dict) else 0,
        "story_bible": story_bible,
        "missing_assets": lock.get("missing_assets", []) if isinstance(lock, dict) else [],
        "reference_progress": lock.get("reference_progress", []) if isinstance(lock, dict) else [],
        "reference_status": _reference_status(series),
        "agency_team_status": summarize_video_agency_team(agency_team),
    }


def _lifecycle_http_error(exc: AssetLifecycleError) -> HTTPException:
    status_code = 404 if exc.code in ("SERIES_NOT_FOUND", "ASSET_NOT_FOUND") else 409
    return HTTPException(status_code, {"code": exc.code, "message": exc.message, "details": exc.details})


@router.get("/{series_id}/agency-console")
def get_agency_console(series_id: str, db: Session = Depends(get_db),
                       _: str = Depends(require_role("admin"))):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
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


async def _run_style_lock_job(series_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    db = db or SessionLocal()
    story_bible: dict = {}
    missing_assets: list[dict] = []
    try:
        series = db.query(Series).filter(Series.id == series_id).first()
        if not series:
            return {"ok": False, "status": "failed", "error": "Series not found"}

        current = (series.story_bible_json or {}).get("style_lock", {})
        version = int(current.get("version") or 1) if isinstance(current, dict) else 1
        _set_style_lock_state(db, series, status="locking", version=version, locked=False)

        await _ensure_series_assets(series, db)
        db.commit()
        db.refresh(series)

        missing_assets = await _fill_reference_assets(series, db)

        story_bible = _build_story_bible(series, version, missing_assets)
        style_lock = story_bible["style_lock"]
        try:
            runtime_config = resolve_runtime_model_config(db, "llm_agency_expert_review")
        except RuntimeModelConfigError as exc:
            style_lock["agency_trace"] = _missing_agency_trace("style_lock", exc)
        else:
            try:
                style_lock["agency_trace"] = await asyncio.wait_for(
                    AgencyOrchestrator().run_style_lock_review(
                        db,
                        series_id=series.id,
                        stage_context={"style_lock": style_lock},
                        runtime_config=runtime_config,
                    ),
                    timeout=STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                style_lock["agency_trace"] = _timeout_agency_trace(
                    "style_lock",
                    STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS,
                )
        if _agency_trace_blocks(style_lock.get("agency_trace")):
            style_lock["locked"] = False
        style_lock["status"] = "locked" if style_lock.get("locked") else "blocked"
        style_lock["lock_completed_at"] = _utc_now_iso()
        style_lock["lock_error"] = None
        series.story_bible_json = story_bible
        flag_modified(series, "story_bible_json")
        _record_style_lock_series_bible_artifact(db, series, story_bible, missing_assets=missing_assets)
        db.commit()
        return {
            "ok": True,
            "status": style_lock["status"],
            "story_bible": story_bible,
            "missing_assets": missing_assets,
            "audit_reports": [],
        }
    except Exception as exc:
        db.rollback()
        series = db.query(Series).filter(Series.id == series_id).first()
        if series:
            _set_style_lock_state(db, series, status="failed", locked=False, error=str(exc))
        raise
    finally:
        if owns_session:
            db.close()


async def _run_style_lock_worker_step(db: Session, *, lease_id: str, batch_size: int = 1) -> dict:
    limit = max(1, min(int(batch_size or 1), 20))
    items: list[dict] = []
    for _ in range(limit):
        job = claim_next_job(
            db,
            lease_id=lease_id,
            lease_seconds=STYLE_LOCK_JOB_LEASE_SECONDS,
            stage=STYLE_LOCK_STAGE,
        )
        if not job:
            break
        try:
            job.status = JOB_RUNNING
            job.started_at = job.started_at or bj_now()
            db.commit()
            result = await _run_style_lock_job(job.target_id, db=db)
            completed_job = mark_job_completed(
                db,
                job.id,
                expected_lease_id=lease_id,
                allowed_statuses=(JOB_LEASED, JOB_RUNNING),
            )
            plan = db.query(ProductionPlan).filter(ProductionPlan.id == completed_job.plan_id).first()
            if plan:
                plan.status = PLAN_COMPLETED
                db.commit()
            items.append({
                "ok": True,
                "job_id": completed_job.id,
                "series_id": completed_job.target_id,
                "status": completed_job.status,
                "result": result,
            })
        except Exception as exc:
            logger.exception("Style lock worker failed job %s", job.id)
            failed_job = fail_job(db, job.id, "STYLE_LOCK_JOB_FAILED", str(exc), retryable=True)
            items.append({
                "ok": False,
                "job_id": failed_job.id,
                "series_id": failed_job.target_id,
                "status": failed_job.status,
                "error": str(exc),
            })

    remaining = (
        db.query(ProductionJob)
        .filter(ProductionJob.target_type == "series")
        .filter(ProductionJob.stage == STYLE_LOCK_STAGE)
        .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
        .count()
    )
    return {
        "ok": True,
        "lease_id": lease_id,
        "processed": len(items),
        "remaining": remaining,
        "items": items,
    }


async def _run_story_plan_job(series_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    db = db or SessionLocal()
    try:
        series = db.query(Series).filter(Series.id == series_id).first()
        if not series:
            return {"ok": False, "status": "failed", "error": "Series not found"}

        current = (series.story_bible_json or {}).get("story_planning", {})
        version = int(current.get("version") or 1) if isinstance(current, dict) else 1
        _set_story_planning_state(db, series, status="running", version=version)
        result = await generate_series_story_plan(db, series_id)
        trace = result.model_trace if hasattr(result, "model_trace") else {}
        terminal_status = "fallback" if isinstance(trace, dict) and trace.get("stage_status") == "fallback" else "completed"
        result_payload = result.__dict__ if hasattr(result, "__dict__") else result
        db.refresh(series)
        story_planning = _set_story_planning_state(
            db,
            series,
            status=terminal_status,
            version=version,
            result=result_payload if isinstance(result_payload, dict) else {"ok": True},
        )
        return {
            "ok": True,
            "status": terminal_status,
            "series_id": series_id,
            "story_planning": story_planning,
            "result": result_payload,
        }
    except Exception as exc:
        db.rollback()
        series = db.query(Series).filter(Series.id == series_id).first()
        if series:
            _set_story_planning_state(db, series, status="failed", error=str(exc))
        raise
    finally:
        if owns_session:
            db.close()


async def _run_story_plan_worker_step(db: Session, *, lease_id: str, batch_size: int = 1) -> dict:
    limit = max(1, min(int(batch_size or 1), 20))
    items: list[dict] = []
    for _ in range(limit):
        job = claim_next_job(
            db,
            lease_id=lease_id,
            lease_seconds=STORY_PLANNING_JOB_LEASE_SECONDS,
            stage=STORY_PLANNING_STAGE,
        )
        if not job:
            break
        try:
            job.status = JOB_RUNNING
            job.started_at = job.started_at or bj_now()
            db.commit()
            result = await _run_story_plan_job(job.target_id, db=db)
            completed_job = mark_job_completed(
                db,
                job.id,
                expected_lease_id=lease_id,
                allowed_statuses=(JOB_LEASED, JOB_RUNNING),
            )
            plan = db.query(ProductionPlan).filter(ProductionPlan.id == completed_job.plan_id).first()
            if plan:
                plan.status = PLAN_COMPLETED
                db.commit()
            items.append({
                "ok": True,
                "job_id": completed_job.id,
                "series_id": completed_job.target_id,
                "status": completed_job.status,
                "result": result,
            })
        except Exception as exc:
            logger.exception("Story planning worker failed job %s", job.id)
            failed_job = fail_job(db, job.id, "STORY_PLANNING_JOB_FAILED", str(exc), retryable=True)
            items.append({
                "ok": False,
                "job_id": failed_job.id,
                "series_id": failed_job.target_id,
                "status": failed_job.status,
                "error": str(exc),
            })

    remaining = (
        db.query(ProductionJob)
        .filter(ProductionJob.target_type == "series")
        .filter(ProductionJob.stage == STORY_PLANNING_STAGE)
        .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
        .count()
    )
    return {
        "ok": True,
        "lease_id": lease_id,
        "processed": len(items),
        "remaining": remaining,
        "items": items,
    }


@router.post("/style-lock/worker-step")
async def run_style_lock_worker_step(
    body: StyleLockWorkerStepRequest = StyleLockWorkerStepRequest(),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin")),
):
    return await _run_style_lock_worker_step(db, lease_id=body.lease_id, batch_size=body.batch_size)


@router.post("/story-plan/worker-step")
async def run_story_plan_worker_step(
    body: StoryPlanWorkerStepRequest = StoryPlanWorkerStepRequest(),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin")),
):
    return await _run_story_plan_worker_step(db, lease_id=body.lease_id, batch_size=body.batch_size)


@router.post("/{series_id}/style-lock", response_model=StyleLockResponse)
async def lock_series_style(series_id: str, db: Session = Depends(get_db),
                            user = Depends(verify_admin_token)):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")

    active_job = _active_style_lock_job(db, series.id)
    if active_job:
        raise _style_lock_in_progress_error()

    story_bible = dict(series.story_bible_json or {})
    current = story_bible.get("style_lock", {})
    version = int(current.get("version") or 0) + 1 if isinstance(current, dict) else 1
    job = _enqueue_style_lock_job(db, series, version)
    db.refresh(series)
    lock = _set_style_lock_state(db, series, status="locking", version=version, locked=False)
    lock["job_id"] = job.id
    story_bible = dict(series.story_bible_json or {})
    story_bible["style_lock"] = lock
    series.story_bible_json = story_bible
    flag_modified(series, "story_bible_json")
    db.commit()

    return {
        "ok": True,
        "status": "locking",
        "story_bible": {"style_lock": lock},
        "missing_assets": [],
        "audit_reports": [],
    }

@router.post("")
def create_series(body: SeriesCreate, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    s = Series(**body.model_dump())
    db.add(s)
    db.flush()  # 确保 s.id 已生成，满足 Episode FK 约束
    for ep_num in range(1, body.total_episodes + 1):
        db.add(Episode(series_id=s.id, episode_number=ep_num, status="pending"))
    db.commit(); db.refresh(s)
    return {"ok": True, "series": _series_dict(s)}

@router.get("/{series_id}")
def get_series(series_id: str, db: Session = Depends(get_db),
               _: str = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    episodes = db.query(Episode).filter(
        Episode.series_id == series_id
    ).order_by(Episode.episode_number).all()
    active_runs = _active_video_runs_by_episode(db, series_id)
    episode_payloads = []
    for episode in episodes:
        payload = _episode_dict_with_video_run(episode, active_runs.get(episode.id))
        payload["asset_scope"] = _episode_asset_scope_payload(db, episode)
        episode_payloads.append(payload)
    return {"ok": True, "series": _series_dict(s, include_linked_assets=True),
            "episodes": episode_payloads}


@router.post("/{series_id}/ensure-episodes")
def ensure_series_episodes(series_id: str, db: Session = Depends(get_db),
                           user = Depends(verify_admin_token)):
    try:
        result = ensure_episode_placeholders(db, series_id)
        continuity = ensure_series_continuity_artifacts(db, series_id)
    except ValueError as exc:
        if str(exc) == "series_not_found":
            raise HTTPException(404, "Series not found")
        raise
    return {
        "ok": True,
        "series_id": result.series_id,
        "target_episode_count": result.target_episode_count,
        "existing_episode_numbers": result.existing_episode_numbers,
        "created_episode_numbers": result.created_episode_numbers,
        "created_continuity_ledger": continuity.created_continuity_ledger,
        "created_outline_episode_numbers": continuity.created_outline_episode_numbers,
    }


@router.post("/{series_id}/story-plan")
async def create_series_story_plan(series_id: str, db: Session = Depends(get_db),
                                   user = Depends(verify_admin_token)):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    if _active_story_plan_job(db, series.id):
        raise _story_planning_in_progress_error()
    completed_payload = _completed_story_plan_payload(db, series)
    if completed_payload:
        return completed_payload

    story_bible = dict(series.story_bible_json or {})
    current = story_bible.get("story_planning", {})
    version = int(current.get("version") or 0) + 1 if isinstance(current, dict) else 1
    job = _enqueue_story_plan_job(db, series, version)
    db.refresh(series)
    story_planning = _set_story_planning_state(db, series, status="queued", version=version, job_id=job.id)
    return {
        "ok": True,
        "status": "planning",
        "series_id": series.id,
        "job_id": job.id,
        "story_planning": story_planning,
    }


@router.put("/{series_id}")
def update_series(series_id: str, body: SeriesUpdate, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return {"ok": True, "series": _series_dict(s)}

@router.delete("/{series_id}")
def delete_series(series_id: str, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    try:
        result = delete_or_archive_series(db, series_id)
    except AssetLifecycleError as exc:
        raise _lifecycle_http_error(exc)
    return {"ok": True, **result}

# === M2M 关联 ===

@router.post("/{series_id}/characters/{character_id}")
def link_character(series_id: str, character_id: str, db: Session = Depends(get_db),
                   user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    c = db.query(Character).filter(Character.id == character_id).first()
    if not s or not c:
        raise HTTPException(404, "Series or Character not found")
    s.characters.append(c)
    db.commit()
    return {"ok": True}

@router.delete("/{series_id}/characters/{character_id}")
def unlink_character(series_id: str, character_id: str, db: Session = Depends(get_db),
                     user = Depends(verify_admin_token)):
    try:
        result = unlink_character_from_series(db, series_id, character_id)
    except AssetLifecycleError as exc:
        raise _lifecycle_http_error(exc)
    return {"ok": True, **result}

@router.post("/{series_id}/scenes/{scene_id}")
def link_scene(series_id: str, scene_id: str, db: Session = Depends(get_db),
               user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    sc = db.query(Scene).filter(Scene.id == scene_id).first()
    if not s or not sc:
        raise HTTPException(404, "Series or Scene not found")
    s.scenes.append(sc)
    db.commit()
    return {"ok": True}

# === Episode 管理 ===

@router.delete("/{series_id}/scenes/{scene_id}")
def unlink_scene(series_id: str, scene_id: str, db: Session = Depends(get_db),
                 user = Depends(verify_admin_token)):
    try:
        result = unlink_scene_from_series(db, series_id, scene_id)
    except AssetLifecycleError as exc:
        raise _lifecycle_http_error(exc)
    return {"ok": True, **result}


@router.post("/{series_id}/episodes/{episode_id}/script")
async def generate_episode_script(
    series_id: str,
    episode_id: str,
    body: EpisodeScriptGenerationRequest = EpisodeScriptGenerationRequest(),
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        result = await generate_episode_script_storyboard(
            db,
            series_id=series_id,
            episode_id=episode_id,
            target_duration_seconds=body.target_duration_seconds,
        )
    except ValueError as exc:
        if str(exc) == "series_not_found":
            raise HTTPException(404, "Series not found")
        if str(exc) == "episode_not_found":
            raise HTTPException(404, "Episode not found")
        raise
    except Exception as exc:
        raise HTTPException(500, {
            "code": "EPISODE_SCRIPT_GENERATION_FAILED",
            "message": str(exc),
        })
    return {"ok": True, **result}


@router.put("/{series_id}/episodes/{episode_id}")
def update_episode(series_id: str, episode_id: str, body: EpisodeUpdate,
                   db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    ep = db.query(Episode).filter(
        Episode.id == episode_id, Episode.series_id == series_id
    ).first()
    if not ep:
        raise HTTPException(404, "Episode not found")
    payload = body.model_dump(exclude_none=True)
    for k, v in payload.items():
        setattr(ep, k, v)
    _record_episode_update_text_artifacts(db, ep, payload, user)
    db.commit()
    return {"ok": True}
