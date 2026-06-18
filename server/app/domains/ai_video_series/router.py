"""系列 + 剧集管理 API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import require_role, verify_admin_token
from app.db_models import Series, Episode, Character, Scene
from app.domains.ai_video_series import story_planning, style_lock
from app.domains.ai_video_series.artifacts import (
    actor_id,
    completed_story_plan_payload,
    record_episode_update_text_artifacts,
    storyboard_text_values,
    story_plan_artifact_summary,
)
from app.domains.ai_video_series.read_models import (
    active_video_runs_by_episode,
    agency_console_payload,
    character_reference_urls,
    episode_asset_scope_payload,
    episode_asset_usage_items,
    episode_dict,
    episode_dict_with_video_run,
    reference_status,
    scene_reference_urls,
    series_char_dict,
    series_dict,
    series_scene_dict,
)
from app.domains.ai_video_series.schemas import (
    EpisodeScriptGenerationRequest,
    EpisodeUpdate,
    SeriesCreate,
    SeriesUpdate,
    StoryPlanWorkerStepRequest,
    StyleLockResponse,
    StyleLockWorkerStepRequest,
)
from app.services.asset_lifecycle_service import (
    AssetLifecycleError,
    delete_or_archive_series,
    unlink_character_from_series,
    unlink_scene_from_series,
)
from app.services.production_run_service import generate_episode_script_storyboard
from app.services.series_planning_service import ensure_episode_placeholders, ensure_series_continuity_artifacts

router = APIRouter(prefix="/api/series", tags=["series"])

_active_video_runs_by_episode = active_video_runs_by_episode
_agency_console_payload = agency_console_payload
_actor_id = actor_id
_character_reference_urls = character_reference_urls
_completed_story_plan_payload = completed_story_plan_payload
_episode_asset_scope_payload = episode_asset_scope_payload
_episode_asset_usage_items = episode_asset_usage_items
_episode_dict = episode_dict
_episode_dict_with_video_run = episode_dict_with_video_run
_record_episode_update_text_artifacts = record_episode_update_text_artifacts
_reference_status = reference_status
_scene_reference_urls = scene_reference_urls
_series_char_dict = series_char_dict
_series_dict = series_dict
_series_scene_dict = series_scene_dict
_story_plan_artifact_summary = story_plan_artifact_summary
_storyboard_text_values = storyboard_text_values

_missing_agency_trace = style_lock.missing_agency_trace
_timeout_agency_trace = style_lock.timeout_agency_trace
_agency_trace_blocks = style_lock.agency_trace_blocks
_utc_now_iso = style_lock.utc_now_iso
_style_lock_status = style_lock.style_lock_status
_upsert_reference_progress_item = style_lock.upsert_reference_progress_item
_record_reference_slot_progress = style_lock.record_reference_slot_progress
_stored_reference_prompt_matches = style_lock.stored_reference_prompt_matches
_set_style_lock_state = style_lock.set_style_lock_state
_record_style_lock_series_bible_artifact = style_lock.record_style_lock_series_bible_artifact
_style_lock_in_progress_error = style_lock.style_lock_in_progress_error
_active_style_lock_job = style_lock.active_style_lock_job
_enqueue_style_lock_job = style_lock.enqueue_style_lock_job
_parse_json_with_key = style_lock.parse_json_with_key
_generate_reference_image = style_lock.generate_reference_image
_generate_reference_image_isolated = style_lock.generate_reference_image_isolated
_ensure_series_assets = style_lock.ensure_series_assets
_build_story_bible = style_lock.build_story_bible
_story_planning_in_progress_error = story_planning.story_planning_in_progress_error
_active_story_plan_job = story_planning.active_story_plan_job
_set_story_planning_state = story_planning.set_story_planning_state
_enqueue_story_plan_job = story_planning.enqueue_story_plan_job
_run_story_plan_job = story_planning.run_story_plan_job
_fill_reference_assets = style_lock.fill_reference_assets
_run_style_lock_job = style_lock.run_style_lock_job
_run_style_lock_worker_step = style_lock.run_style_lock_worker_step
_run_story_plan_worker_step = story_planning.run_story_plan_worker_step
STYLE_LOCK_STAGE = style_lock.STYLE_LOCK_STAGE
STYLE_LOCK_ACTIVE_JOB_STATUSES = style_lock.STYLE_LOCK_ACTIVE_JOB_STATUSES
STYLE_LOCK_JOB_LEASE_SECONDS = style_lock.STYLE_LOCK_JOB_LEASE_SECONDS
STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS = style_lock.STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS
STYLE_LOCK_REFERENCE_CONCURRENCY = style_lock.STYLE_LOCK_REFERENCE_CONCURRENCY
AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS = style_lock.AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS
STORY_PLANNING_STAGE = story_planning.STORY_PLANNING_STAGE
STORY_PLANNING_ACTIVE_JOB_STATUSES = story_planning.STORY_PLANNING_ACTIVE_JOB_STATUSES
STORY_PLANNING_JOB_LEASE_SECONDS = story_planning.STORY_PLANNING_JOB_LEASE_SECONDS


def _domain_http_error(exc):
    return HTTPException(exc.status_code, exc.detail)

# === AI 自动生成角色 + 场景 ===

@router.post("/{series_id}/auto-generate")
async def auto_generate_series_assets(series_id: str, db: Session = Depends(get_db),
                                      user = Depends(verify_admin_token)):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    try:
        return await style_lock.auto_generate_series_assets(series, db)
    except style_lock.StyleLockDomainError as exc:
        raise _domain_http_error(exc) from exc


# === Series CRUD ===

@router.get("")
def list_series(db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    all_series = db.query(Series).order_by(Series.updated_at.desc()).all()
    return {"ok": True, "series": [series_dict(s) for s in all_series]}


@router.get("/{series_id}/style-lock")
def get_style_lock(series_id: str, db: Session = Depends(get_db),
                   _: str = Depends(verify_admin_token)):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    return style_lock.style_lock_payload(db, series)


def _lifecycle_http_error(exc: AssetLifecycleError) -> HTTPException:
    status_code = 404 if exc.code in ("SERIES_NOT_FOUND", "ASSET_NOT_FOUND") else 409
    return HTTPException(status_code, {"code": exc.code, "message": exc.message, "details": exc.details})


@router.get("/{series_id}/agency-console")
def get_agency_console(series_id: str, db: Session = Depends(get_db),
                       _: str = Depends(require_role("admin"))):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    return agency_console_payload(db, series, series_id)



@router.post("/style-lock/worker-step")
async def run_style_lock_worker_step(
    body: StyleLockWorkerStepRequest = StyleLockWorkerStepRequest(),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin")),
):
    return await style_lock.run_style_lock_worker_step(db, lease_id=body.lease_id, batch_size=body.batch_size)


@router.post("/story-plan/worker-step")
async def run_story_plan_worker_step(
    body: StoryPlanWorkerStepRequest = StoryPlanWorkerStepRequest(),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin")),
):
    return await story_planning.run_story_plan_worker_step(db, lease_id=body.lease_id, batch_size=body.batch_size)


@router.post("/{series_id}/style-lock", response_model=StyleLockResponse)
async def lock_series_style(series_id: str, db: Session = Depends(get_db),
                            user = Depends(verify_admin_token)):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    try:
        return style_lock.start_style_lock(db, series)
    except style_lock.StyleLockDomainError as exc:
        raise _domain_http_error(exc) from exc

@router.post("")
def create_series(body: SeriesCreate, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    s = Series(**body.model_dump())
    db.add(s)
    db.flush()  # 确保 s.id 已生成，满足 Episode FK 约束
    for ep_num in range(1, body.total_episodes + 1):
        db.add(Episode(series_id=s.id, episode_number=ep_num, status="pending"))
    db.commit(); db.refresh(s)
    return {"ok": True, "series": series_dict(s)}

@router.get("/{series_id}")
def get_series(series_id: str, db: Session = Depends(get_db),
               _: str = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    episodes = db.query(Episode).filter(
        Episode.series_id == series_id
    ).order_by(Episode.episode_number).all()
    active_runs = active_video_runs_by_episode(db, series_id)
    episode_payloads = []
    for episode in episodes:
        payload = episode_dict_with_video_run(episode, active_runs.get(episode.id))
        payload["asset_scope"] = episode_asset_scope_payload(db, episode)
        episode_payloads.append(payload)
    return {"ok": True, "series": series_dict(s, include_linked_assets=True),
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
    try:
        return story_planning.start_story_plan(db, series)
    except story_planning.StoryPlanningDomainError as exc:
        raise _domain_http_error(exc) from exc


@router.put("/{series_id}")
def update_series(series_id: str, body: SeriesUpdate, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return {"ok": True, "series": series_dict(s)}

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
    record_episode_update_text_artifacts(db, ep, payload, user)
    db.commit()
    return {"ok": True}


__all__ = [
    "router",
    "SeriesCreate",
    "SeriesUpdate",
    "EpisodeUpdate",
    "StyleLockResponse",
    "StyleLockWorkerStepRequest",
    "StoryPlanWorkerStepRequest",
    "EpisodeScriptGenerationRequest",
]
