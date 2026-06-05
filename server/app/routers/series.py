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
from sqlalchemy.orm import Session
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
from app.services.asset_lifecycle_service import (
    AssetLifecycleError,
    delete_or_archive_series,
    unlink_character_from_series,
    unlink_scene_from_series,
)
from app.services.reference_asset_service import ReferenceAssetError, generate_reference_url, reference_url_is_usable
from app.services.production_queue_service import claim_next_job, fail_job, mark_job_completed
from app.services.production_status import JOB_LEASED, JOB_QUEUED, JOB_RETRY_WAIT, JOB_RUNNING, PLAN_COMPLETED, PLAN_READY
from app.services.runtime_model_config import RuntimeModelConfigError, resolve_runtime_model_config
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


STYLE_LOCK_STAGE = "style_lock"
STYLE_LOCK_ACTIVE_JOB_STATUSES = (JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT)
STYLE_LOCK_JOB_LEASE_SECONDS = 3600
STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS", "30"))


def _style_lock_in_progress_error() -> HTTPException:
    return HTTPException(409, {
        "code": "STYLE_LOCK_IN_PROGRESS",
        "message": "Style lock is already running for this series.",
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
            db, _CHAR_SYSTEM, char_prompt, max_tokens=4096, temperature=0.8
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
            db, _SCENE_SYSTEM, scene_prompt, max_tokens=4096, temperature=0.8
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


_VIDEO_RUN_TERMINAL_STATUSES = {"completed", "done", "failed", "cancelled", "canceled"}


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
            context = {
                "series_id": series.id,
                "style_lock_version": style_lock_version,
                "asset_type": "character",
                "asset_id": character.id,
                "slot": field,
            }
            url = await _generate_reference_image(db, prompt, destination_context=context)
            if url:
                setattr(character, field, url)
                _record_reference_slot_progress(
                    db,
                    series,
                    character,
                    asset_type="character",
                    slot=field,
                    label=angle_label,
                    status="ready",
                    prompt=prompt,
                    url=url,
                )
            else:
                item = {
                    "type": "character_reference",
                    "id": character.id,
                    "name": character.name,
                    "slot": field,
                }
                missing.append(item)
                _record_reference_slot_progress(
                    db,
                    series,
                    character,
                    asset_type="character",
                    slot=field,
                    label=angle_label,
                    status="failed",
                    prompt=prompt,
                    error="Reference image generation failed",
                )

    for scene in series.scenes:
        for field, reference_label in _SCENE_REFERENCE_SLOTS:
            prompt = f"{reference_label}, consistent palette, lighting, environment design, and series style. "
            prompt += f"Scene: {scene.name}. Location: {scene.location_desc or ''}. Lighting: {scene.lighting or ''}. Mood: {scene.mood or ''}."
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
            context = {
                "series_id": series.id,
                "style_lock_version": style_lock_version,
                "asset_type": "scene",
                "asset_id": scene.id,
                "slot": field,
            }
            url = await _generate_reference_image(db, prompt, destination_context=context)
            if url:
                setattr(scene, field, url)
                _record_reference_slot_progress(
                    db,
                    series,
                    scene,
                    asset_type="scene",
                    slot=field,
                    label=reference_label,
                    status="ready",
                    prompt=prompt,
                    url=url,
                )
            else:
                item = {
                    "type": "scene_reference",
                    "id": scene.id,
                    "name": scene.name,
                    "slot": field,
                }
                missing.append(item)
                _record_reference_slot_progress(
                    db,
                    series,
                    scene,
                    asset_type="scene",
                    slot=field,
                    label=reference_label,
                    status="failed",
                    prompt=prompt,
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


@router.post("/style-lock/worker-step")
async def run_style_lock_worker_step(
    body: StyleLockWorkerStepRequest = StyleLockWorkerStepRequest(),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin")),
):
    return await _run_style_lock_worker_step(db, lease_id=body.lease_id, batch_size=body.batch_size)


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
def get_series(series_id: str, db: Session = Depends(get_db)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    episodes = db.query(Episode).filter(
        Episode.series_id == series_id
    ).order_by(Episode.episode_number).all()
    active_runs = _active_video_runs_by_episode(db, series_id)
    return {"ok": True, "series": _series_dict(s, include_linked_assets=True),
            "episodes": [_episode_dict_with_video_run(e, active_runs.get(e.id)) for e in episodes]}

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

@router.put("/{series_id}/episodes/{episode_id}")
def update_episode(series_id: str, episode_id: str, body: EpisodeUpdate,
                   db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    ep = db.query(Episode).filter(
        Episode.id == episode_id, Episode.series_id == series_id
    ).first()
    if not ep:
        raise HTTPException(404, "Episode not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ep, k, v)
    db.commit()
    return {"ok": True}
