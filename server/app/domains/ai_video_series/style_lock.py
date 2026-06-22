"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 style_lock 相关业务规则、状态转换和外部系统边界。
"""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
import os

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.config import bj_now
from app.database import SessionLocal
from app.db.models.ai_video_series import ProductionJob, ProductionPlan, Series
from app.db.models import Character, Scene
from app.domains.ai_video_series.read_models import (
    character_reference_urls,
    reference_status,
    scene_reference_urls,
    series_char_dict,
    series_scene_dict,
)
from app.domains.ai_video_series.langchain_runtime.agent_runner import run_structured_ai_video_json
from app.domains.model_configuration.ai_generator import ai_generator
from app.domains.agency_operations.agency_orchestrator import AgencyOrchestrator
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
from app.domains.creative_library.reference_asset_service import (
    ReferenceAssetError,
    SCENE_EMPTY_PLATE_INSTRUCTION,
    generate_reference_url,
    reference_url_is_usable,
)
from app.domains.video_production.production_queue_service import claim_next_job, fail_job, mark_job_completed
from app.domains.video_production.production_status import (
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
    JOB_RUNNING,
    PLAN_COMPLETED,
    PLAN_READY,
)
from app.domains.model_configuration.runtime_model_config import RuntimeModelConfigError, resolve_runtime_model_config
from app.domains.agency_operations.video_agency_team import (
    build_video_agency_team,
    ensure_video_agency_team,
    summarize_video_agency_team,
)
from app.domains.creative_library.visual_style_inference_service import (
    append_visual_style_constraints,
    infer_visual_style_from_story,
    merge_visual_style,
    reference_prompt_matches_visual_style,
)


logger = logging.getLogger(__name__)

STYLE_LOCK_STAGE = "style_lock"
STYLE_LOCK_ACTIVE_JOB_STATUSES = (JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT)
STYLE_LOCK_JOB_LEASE_SECONDS = 3600
STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS", "30"))
AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_ASSET_MODEL_TIMEOUT_SECONDS", "180"))

_CHAR_SYSTEM = """你是一位资深的编剧和角色设计师。根据故事概要生成详细的角色档案。
输出必须是合法的 JSON，不要包含 markdown 代码块标记。每个角色包含所有要求字段。
appearance_desc 要足够详细（50-100字），用于 AI 图像生成。角色之间要有区分度。"""

_SCENE_SYSTEM = """你是一位资深的电影导演和场景设计师。根据故事概要生成详细的场景描述。
输出必须是合法的 JSON，不要包含 markdown 代码块标记。每个场景包含所有要求字段。
location_desc 要足够详细（50-100字），用于 AI 图像生成。场景之间要有区分度。"""

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


class StyleLockDomainError(RuntimeError):
    """业务类：承载 StyleLockDomainError 相关的数据结构、状态或业务协作。

    类参数：detail、status_code 承载该类的业务配置、状态或数据字段。
    """
    def __init__(self, status_code: int, detail: object):
        """初始化业务对象依赖，保存后续流程需要的运行上下文。

        入参：status_code、detail 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


async def auto_generate_series_assets(series: Series, db: Session) -> dict:
    """业务函数：处理 auto_generate_series_assets 对应的业务流程、校验或数据转换。

    入参：series、db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not series.logline:
        raise StyleLockDomainError(400, "请先填写系列的故事概要 (logline)")

    text = series.logline
    genre = series.genre

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
        char_data = await run_structured_ai_video_json(
            system_prompt=_CHAR_SYSTEM,
            user_prompt=char_prompt,
            runtime_config=resolve_runtime_model_config(db, "script_generation"),
            db=db,
            allowed_tools=["validate_json", "read_series_context"],
        )
    except Exception as e:
        logger.warning("Auto-generate characters failed: %s", e)
        raise StyleLockDomainError(500, f"角色生成失败: {e}")

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
        scene_data = await run_structured_ai_video_json(
            system_prompt=_SCENE_SYSTEM,
            user_prompt=scene_prompt,
            runtime_config=resolve_runtime_model_config(db, "script_generation"),
            db=db,
            allowed_tools=["validate_json", "read_series_context"],
        )
    except Exception as e:
        logger.warning("Auto-generate scenes failed: %s", e)
        raise StyleLockDomainError(500, f"场景生成失败: {e}")

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

    for ch in created_chars:
        series.characters.append(ch)
    for scene in created_scenes:
        series.scenes.append(scene)

    db.commit()

    return {
        "ok": True,
        "characters": [series_char_dict(c) for c in created_chars],
        "scenes": [series_scene_dict(sc) for sc in created_scenes],
    }


def missing_agency_trace(stage: str, exc: Exception) -> dict:
    """业务函数：处理 missing_agency_trace 对应的业务流程、校验或数据转换。

    入参：stage、exc 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "EXPERT_MODEL_CONFIG_MISSING",
        "error_message": str(exc),
    }


def timeout_agency_trace(stage: str, timeout_seconds: float) -> dict:
    """业务函数：处理 timeout_agency_trace 对应的业务流程、校验或数据转换。

    入参：stage、timeout_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "STYLE_LOCK_REVIEW_TIMEOUT",
        "error_message": f"Style lock expert review exceeded {timeout_seconds:g} seconds.",
    }


def agency_trace_blocks(trace: dict | None) -> bool:
    """业务函数：处理 agency_trace_blocks 对应的业务流程、校验或数据转换。

    入参：trace 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return bool(isinstance(trace, dict) and trace.get("stage_status") in {"blocked", "failed"})


def utc_now_iso() -> str:
    """业务函数：处理 utc_now_iso 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return datetime.now(timezone.utc).isoformat()


def style_lock_status(lock: dict | None) -> str:
    """业务函数：处理 style_lock_status 对应的业务流程、校验或数据转换。

    入参：lock 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not isinstance(lock, dict):
        return "unlocked"
    if lock.get("status"):
        return str(lock["status"])
    return "locked" if lock.get("locked") else "unlocked"


def style_lock_payload(db: Session, series: Series) -> dict:
    """业务函数：处理 style_lock_payload 对应的业务流程、校验或数据转换。

    入参：db、series 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
        "status": style_lock_status(lock if isinstance(lock, dict) else None),
        "version": lock.get("version", 0) if isinstance(lock, dict) else 0,
        "story_bible": story_bible,
        "missing_assets": lock.get("missing_assets", []) if isinstance(lock, dict) else [],
        "reference_progress": lock.get("reference_progress", []) if isinstance(lock, dict) else [],
        "reference_status": reference_status(series),
        "agency_team_status": summarize_video_agency_team(agency_team),
    }


def upsert_reference_progress_item(series: Series, item: dict) -> None:
    """业务函数：处理 upsert_reference_progress_item 对应的业务流程、校验或数据转换。

    入参：series、item 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    story_bible = dict(series.story_bible_json or {})
    lock = dict(story_bible.get("style_lock") or {})
    progress = list(lock.get("reference_progress") or [])
    key = (item.get("asset_type"), item.get("asset_id"), item.get("slot"))
    index = next((
        idx for idx, current in enumerate(progress)
        if (current.get("asset_type"), current.get("asset_id"), current.get("slot")) == key
    ), None)
    payload = {**item, "updated_at": utc_now_iso()}
    if index is None:
        progress.append(payload)
    else:
        progress[index] = {**progress[index], **payload}
    lock["reference_progress"] = progress
    story_bible["style_lock"] = lock
    series.story_bible_json = story_bible
    flag_modified(series, "story_bible_json")


def record_reference_slot_progress(
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
    """业务函数：处理 record_reference_slot_progress 对应的业务流程、校验或数据转换。

    入参：db、series、row、asset_type、slot、label、status、prompt、url、error 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
        "updated_at": utc_now_iso(),
    }
    meta_json["reference_generation"] = reference_generation
    row.meta_json = meta_json
    flag_modified(row, "meta_json")
    upsert_reference_progress_item(series, {
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


def stored_reference_prompt_matches(row, slot: str, visual_style: dict) -> bool:
    """业务函数：处理 stored_reference_prompt_matches 对应的业务流程、校验或数据转换。

    入参：row、slot、visual_style 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    meta_json = row.meta_json or {}
    reference_generation = meta_json.get("reference_generation") if isinstance(meta_json, dict) else {}
    slot_meta = reference_generation.get(slot) if isinstance(reference_generation, dict) else {}
    stored_prompt = slot_meta.get("prompt") if isinstance(slot_meta, dict) else None
    return reference_prompt_matches_visual_style(stored_prompt, visual_style)


def set_style_lock_state(
    db: Session,
    series: Series,
    *,
    status: str,
    version: int | None = None,
    locked: bool | None = None,
    error: str | None = None,
) -> dict:
    """业务函数：处理 set_style_lock_state 对应的业务流程、校验或数据转换。

    入参：db、series、status、version、locked、error 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    story_bible = dict(series.story_bible_json or {})
    current = dict(story_bible.get("style_lock") or {})
    current["status"] = status
    if version is not None:
        current["version"] = version
    if locked is not None:
        current["locked"] = locked
    current["series_id"] = series.id
    if status == "locking":
        current["lock_started_at"] = utc_now_iso()
        current["lock_completed_at"] = None
        current["lock_error"] = None
        current["missing_assets"] = []
        current["reference_progress"] = []
        current.pop("agency_trace", None)
    elif status in {"locked", "blocked", "failed"}:
        current["lock_completed_at"] = utc_now_iso()
        current["lock_error"] = error
    story_bible["style_lock"] = current
    series.story_bible_json = story_bible
    flag_modified(series, "story_bible_json")
    db.commit()
    db.refresh(series)
    return current


def record_style_lock_series_bible_artifact(
    db: Session,
    series: Series,
    story_bible: dict,
    *,
    missing_assets: list[dict],
) -> None:
    """业务函数：处理 record_style_lock_series_bible_artifact 对应的业务流程、校验或数据转换。

    入参：db、series、story_bible、missing_assets 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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


def style_lock_in_progress_error() -> StyleLockDomainError:
    """业务函数：处理 style_lock_in_progress_error 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return StyleLockDomainError(409, {
        "code": "STYLE_LOCK_IN_PROGRESS",
        "message": "Style lock is already running for this series.",
    })


def active_style_lock_job(db: Session, series_id: str) -> ProductionJob | None:
    """业务函数：处理 active_style_lock_job 对应的业务流程、校验或数据转换。

    入参：db、series_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return (
        db.query(ProductionJob)
        .filter(ProductionJob.target_type == "series")
        .filter(ProductionJob.target_id == series_id)
        .filter(ProductionJob.stage == STYLE_LOCK_STAGE)
        .filter(ProductionJob.status.in_(STYLE_LOCK_ACTIVE_JOB_STATUSES))
        .order_by(ProductionJob.created_at.desc())
        .first()
    )


def enqueue_style_lock_job(db: Session, series: Series, version: int) -> ProductionJob:
    """业务函数：处理 enqueue_style_lock_job 对应的业务流程、校验或数据转换。

    入参：db、series、version 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if active_style_lock_job(db, series.id):
        raise style_lock_in_progress_error()

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
            raise style_lock_in_progress_error()
        raise
    db.refresh(job)
    return job


def start_style_lock(db: Session, series: Series) -> dict:
    """业务函数：处理 start_style_lock 对应的业务流程、校验或数据转换。

    入参：db、series 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    story_bible = dict(series.story_bible_json or {})
    current = story_bible.get("style_lock", {})
    version = int(current.get("version") or 0) + 1 if isinstance(current, dict) else 1
    job = enqueue_style_lock_job(db, series, version)
    db.refresh(series)
    lock = set_style_lock_state(db, series, status="locking", version=version, locked=False)
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


def parse_json_with_key(raw: str, key: str) -> dict:
    """业务函数：处理 parse_json_with_key 对应的业务流程、校验或数据转换。

    入参：raw、key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    key_pos = raw.find('"' + key + '"')
    if key_pos >= 0:
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


async def generate_reference_image(
    db: Session,
    prompt: str,
    *,
    destination_context: dict | None = None,
) -> str | None:
    """业务函数：处理 generate_reference_image 对应的业务流程、校验或数据转换。

    入参：db、prompt、destination_context 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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


async def generate_reference_image_isolated(
    db: Session,
    prompt: str,
    *,
    destination_context: dict,
    semaphore: asyncio.Semaphore,
) -> str | None:
    """业务函数：处理 generate_reference_image_isolated 对应的业务流程、校验或数据转换。

    入参：db、prompt、destination_context、semaphore 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    SessionFactory = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)
    async with semaphore:
        generation_db = SessionFactory()
        try:
            return await generate_reference_image(
                generation_db,
                prompt,
                destination_context=destination_context,
            )
        finally:
            generation_db.close()


async def ensure_series_assets(series: Series, db: Session) -> tuple[list[Character], list[Scene]]:
    """业务函数：处理 ensure_series_assets 对应的业务流程、校验或数据转换。

    入参：series、db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    created_chars: list[Character] = []
    created_scenes: list[Scene] = []

    if not series.characters:
        if not series.logline:
            raise StyleLockDomainError(400, "Series logline is required before style lock")
        char_data = await run_structured_ai_video_json(
            system_prompt=_CHAR_SYSTEM,
            user_prompt=f"Story logline: {series.logline}\nGenre: {series.genre}\nReturn 3-5 characters as JSON with key characters.",
            runtime_config=resolve_runtime_model_config(db, "script_generation"),
            db=db,
            allowed_tools=["validate_json", "read_series_context"],
        )
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
            raise StyleLockDomainError(400, "Series logline is required before style lock")
        scene_data = await run_structured_ai_video_json(
            system_prompt=_SCENE_SYSTEM,
            user_prompt=f"Story logline: {series.logline}\nGenre: {series.genre}\nReturn 3-5 locations as JSON with key scenes.",
            runtime_config=resolve_runtime_model_config(db, "script_generation"),
            db=db,
            allowed_tools=["validate_json", "read_series_context"],
        )
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


async def fill_reference_assets(series: Series, db: Session) -> list[dict]:
    """业务函数：处理 fill_reference_assets 对应的业务流程、校验或数据转换。

    入参：series、db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
            if reference_url_is_usable(getattr(character, field)) and stored_reference_prompt_matches(character, field, visual_style):
                record_reference_slot_progress(
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
            record_reference_slot_progress(
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
            if reference_url_is_usable(getattr(scene, field)) and stored_reference_prompt_matches(scene, field, visual_style):
                record_reference_slot_progress(
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
            record_reference_slot_progress(
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
        """业务函数：处理 run_job 对应的业务流程、校验或数据转换。

        入参：job 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        url = await generate_reference_image_isolated(
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
            record_reference_slot_progress(
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
            record_reference_slot_progress(
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


def build_story_bible(series: Series, version: int, missing_assets: list[dict]) -> dict:
    """业务函数：处理 build_story_bible 对应的业务流程、校验或数据转换。

    入参：series、version、missing_assets 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
            "reference_urls": character_reference_urls(c),
        } for c in series.characters],
        "scenes": [{
            "id": s.id,
            "name": s.name,
            "scene_type": s.scene_type,
            "location_desc": s.location_desc,
            "lighting": s.lighting,
            "mood": s.mood,
            "reference_urls": scene_reference_urls(s),
        } for s in series.scenes],
        "missing_assets": missing_assets,
        "reference_progress": reference_progress,
    }
    return story_bible


async def run_style_lock_job(series_id: str, db: Session | None = None) -> dict:
    """业务函数：处理 run_style_lock_job 对应的业务流程、校验或数据转换。

    入参：series_id、db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
        set_style_lock_state(db, series, status="locking", version=version, locked=False)

        await ensure_series_assets(series, db)
        db.commit()
        db.refresh(series)

        missing_assets = await fill_reference_assets(series, db)

        story_bible = build_story_bible(series, version, missing_assets)
        current_style_lock = story_bible["style_lock"]
        try:
            runtime_config = resolve_runtime_model_config(db, "llm_agency_expert_review")
        except RuntimeModelConfigError as exc:
            current_style_lock["agency_trace"] = missing_agency_trace("style_lock", exc)
        else:
            try:
                current_style_lock["agency_trace"] = await asyncio.wait_for(
                    AgencyOrchestrator().run_style_lock_review(
                        db,
                        series_id=series.id,
                        stage_context={"style_lock": current_style_lock},
                        runtime_config=runtime_config,
                    ),
                    timeout=STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                current_style_lock["agency_trace"] = timeout_agency_trace(
                    "style_lock",
                    STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS,
                )
        if agency_trace_blocks(current_style_lock.get("agency_trace")):
            current_style_lock["locked"] = False
        current_style_lock["status"] = "locked" if current_style_lock.get("locked") else "blocked"
        current_style_lock["lock_completed_at"] = utc_now_iso()
        current_style_lock["lock_error"] = None
        series.story_bible_json = story_bible
        flag_modified(series, "story_bible_json")
        record_style_lock_series_bible_artifact(db, series, story_bible, missing_assets=missing_assets)
        db.commit()
        return {
            "ok": True,
            "status": current_style_lock["status"],
            "story_bible": story_bible,
            "missing_assets": missing_assets,
            "audit_reports": [],
        }
    except Exception as exc:
        db.rollback()
        series = db.query(Series).filter(Series.id == series_id).first()
        if series:
            set_style_lock_state(db, series, status="failed", locked=False, error=str(exc))
        raise
    finally:
        if owns_session:
            db.close()


async def run_style_lock_worker_step(db: Session, *, lease_id: str, batch_size: int = 1) -> dict:
    """业务函数：处理 run_style_lock_worker_step 对应的业务流程、校验或数据转换。

    入参：db、lease_id、batch_size 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
            result = await run_style_lock_job(job.target_id, db=db)
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
