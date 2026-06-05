import math

from sqlalchemy.orm import Session

from app.db_models import (
    Episode,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
)
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.production_observability import record_production_event
from app.services.production_plan_service import create_episode_production_plan, ensure_shot_segments
from app.services.video_production_service import create_run_from_episode, start_image_stage
from app.services.video_production_run_types import LEGACY_EPISODE_RUN, MOCK_SERIES_SCALE, REAL_SHORT_E2E, validate_run_type


REAL_SHORT_MIN_SECONDS = 5
REAL_SHORT_MAX_SECONDS = 28800
PREFERRED_SHOT_SECONDS = 8


def _style_lock(series: Series) -> dict:
    story_bible = series.story_bible_json if isinstance(series.story_bible_json, dict) else {}
    style_lock = story_bible.get("style_lock") or {}
    return style_lock if isinstance(style_lock, dict) else {}


def _production_episode_for_plan(db: Session, plan_id: str, episode_id: str) -> ProductionEpisode:
    return db.query(ProductionEpisode).filter(
        ProductionEpisode.plan_id == plan_id,
        ProductionEpisode.episode_id == episode_id,
    ).one()


def segment_count_for_episode(db: Session, production_episode_id: str) -> int:
    return (
        db.query(ProductionSegment)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == production_episode_id)
        .count()
    )


def create_linked_run(
    db: Session,
    series_id: str,
    episode_id: str,
    production_plan_id: str | None = None,
    run_type: str = LEGACY_EPISODE_RUN,
) -> VideoProductionRun:
    run_type = validate_run_type(run_type)
    query = (
        db.query(ProductionPlan)
        .join(ProductionEpisode, ProductionEpisode.plan_id == ProductionPlan.id)
        .filter(ProductionPlan.series_id == series_id, ProductionEpisode.episode_id == episode_id)
    )
    if production_plan_id:
        query = query.filter(ProductionPlan.id == production_plan_id)
    candidates = query.order_by(ProductionPlan.updated_at.desc(), ProductionPlan.created_at.desc()).all()
    if not candidates:
        raise ProductionRepairableError(
            code=ProductionErrorCode.SEGMENT_PLAN_MISSING,
            message="No production plan exists for this episode.",
            repair_action="Generate episode plan",
            repair_route=f"/series/{series_id}",
            retryable=True,
            affected_ids=[episode_id],
        )
    if len(candidates) > 1 and not production_plan_id:
        raise ProductionRepairableError(
            code=ProductionErrorCode.RUN_LINK_AMBIGUOUS,
            message="This episode has multiple production plans. Choose one before creating a run.",
            repair_action="Repair run-plan link",
            repair_route=f"/series/{series_id}",
            affected_ids=[episode_id],
        )
    plan = candidates[0]
    production_episode = _production_episode_for_plan(db, plan.id, episode_id)
    if segment_count_for_episode(db, production_episode.id) == 0:
        raise ProductionRepairableError(
            code=ProductionErrorCode.SEGMENT_PLAN_MISSING,
            message="No production segments exist for this episode.",
            repair_action="Generate shot segments",
            repair_route=f"/series/{series_id}",
            retryable=True,
            affected_ids=[production_episode.id],
        )

    run = create_run_from_episode(db, series_id, episode_id, commit=False, run_type=run_type)
    run.production_plan_id = plan.id
    run.production_episode_id = production_episode.id
    run.production_link_status = "linked"
    trace = run.model_trace_json or {}
    trace["production_plan_id"] = plan.id
    trace["production_episode_id"] = production_episode.id
    run.model_trace_json = trace
    record_production_event(
        db,
        event_type="run.created",
        run_id=run.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        payload={"link_status": "linked", "run_type": run_type},
    )
    db.commit()
    db.refresh(run)
    return run


def _assert_budget_allows_real_short_start(run_type: str, budget_limit: float | None) -> None:
    if run_type == REAL_SHORT_E2E and (budget_limit is None or float(budget_limit) <= 0):
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_EXCEEDED,
            message="real_short_e2e requires a positive budget_limit before production can start.",
            cause="budget_limit_exhausted",
            repair_action="Set budget_limit greater than 0 or use mock_series_scale for provider-free runs.",
            repair_route="/video-production",
            retryable=True,
        )


def _target_duration_from_storyboard(storyboard: dict) -> int | None:
    frames = storyboard.get("frames") or []
    durations = []
    for frame in frames:
        value = frame.get("duration") or frame.get("duration_seconds")
        if value is not None:
            durations.append(float(value))
    if durations:
        return int(sum(durations))
    total = storyboard.get("total_duration") or storyboard.get("target_duration_seconds")
    return int(total) if total else None


def _dedupe_refs(refs: list[str], limit: int | None = None) -> list[str]:
    deduped = list(dict.fromkeys([ref for ref in refs if ref]))
    return deduped[:limit] if limit else deduped


def _style_item_refs(items: list[dict], item_id: str | None) -> list[str]:
    for item in items:
        if item.get("id") == item_id:
            return item.get("reference_urls") or []
    return []


def _build_style_locked_storyboard(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    target_duration_seconds: int | None,
) -> dict:
    style_lock = _style_lock(series)
    characters = style_lock.get("characters") if isinstance(style_lock.get("characters"), list) else []
    scenes = style_lock.get("scenes") if isinstance(style_lock.get("scenes"), list) else []
    visual_style = style_lock.get("visual_style") if isinstance(style_lock.get("visual_style"), dict) else {}
    style_refs = _dedupe_refs(visual_style.get("reference_urls") or [], 3)
    duration = int(target_duration_seconds or series.target_duration or episode.duration_seconds or 60)
    frame_count = max(1, math.ceil(duration / PREFERRED_SHOT_SECONDS))
    base_duration = round(duration / frame_count, 2)
    character_ids = [item.get("id") for item in characters if item.get("id")]
    default_character_ids = character_ids[:1]
    frames = []
    for index in range(frame_count):
        scene = scenes[index % len(scenes)] if scenes else {}
        scene_id = scene.get("id")
        character_reference_urls = []
        for character_id in default_character_ids:
            character_reference_urls.extend(_style_item_refs(characters, character_id))
        style_reference_urls = _dedupe_refs((scene.get("reference_urls") or []) + style_refs, 3)
        reference_urls = _dedupe_refs(character_reference_urls[:9] + style_reference_urls)
        frame_id = f"frame-{index + 1:03d}"
        frames.append({
            "index": index,
            "frame_id": frame_id,
            "narration": episode.title or series.logline or series.title or "继续推进本集叙事。",
            "image_prompt": "\n".join(part for part in [
                series.logline or series.title or "Generate the next coherent shot.",
                f"Scene: {scene.get('name')}" if scene.get("name") else "",
                f"Visual style: {visual_style.get('prompt')}" if visual_style.get("prompt") else "",
                "Keep character identity, outfit, lighting, color palette, and lens language consistent with the locked references.",
            ] if part),
            "duration": base_duration if index < frame_count - 1 else round(duration - base_duration * (frame_count - 1), 2),
            "audio_mode": "tts",
            "character_ids": default_character_ids,
            "scene_id": scene_id,
            "reference_urls": reference_urls,
            "character_reference_urls": _dedupe_refs(character_reference_urls, 9),
            "style_reference_urls": style_reference_urls,
            "reference_instructions": (
                "Use @Image 1 to lock character face, hairstyle, outfit, and body proportions. "
                "Use the scene/style references to lock lighting, palette, and environment continuity."
            ) if reference_urls else "",
            "continuity_notes": "Fallback storyboard generated from locked style because the episode had no persisted storyboard.",
            "shot_type": ("wide", "medium", "close_up")[index % 3],
            "camera_movement": "static",
            "action": "continue the episode beat",
            "emotion": "natural",
        })
    storyboard = {
        "series_id": series.id,
        "episode_id": episode.id,
        "style_lock_version": style_lock.get("version", 0),
        "planner_mode": "style_lock_fallback",
        "frames": frames,
        "frame_count": len(frames),
        "total_duration": sum(float(frame["duration"]) for frame in frames),
        "edit_packaging": style_lock.get("edit_packaging", {}),
        "quality_gates": style_lock.get("quality_gates", {}),
    }
    episode.storyboard_json = storyboard
    db.commit()
    return storyboard


def _assert_real_short_duration(run_type: str, duration_seconds: int | None) -> None:
    if run_type != REAL_SHORT_E2E:
        return
    if duration_seconds is None or not REAL_SHORT_MIN_SECONDS <= int(duration_seconds) <= REAL_SHORT_MAX_SECONDS:
        raise ProductionRepairableError(
            code=ProductionErrorCode.INVALID_RUN_TYPE,
            message=(
                f"real_short_e2e target_duration_seconds must be at least {REAL_SHORT_MIN_SECONDS} seconds "
                f"and no more than {REAL_SHORT_MAX_SECONDS} seconds."
            ),
            cause="invalid_duration",
            repair_action=(
                f"Set target_duration_seconds between {REAL_SHORT_MIN_SECONDS} and {REAL_SHORT_MAX_SECONDS}, "
                "then let the production plan split the story into short segments."
            ),
            repair_route="/video-production",
            retryable=True,
        )


async def start_episode_production(
    db: Session,
    *,
    series_id: str,
    episode_id: str,
    target_duration_seconds: int | None = None,
    budget_limit: float | None = None,
    autostart_images: bool = True,
    run_type: str = LEGACY_EPISODE_RUN,
    auto_repair_policy: dict | None = None,
) -> VideoProductionRun:
    run_type = validate_run_type(run_type)
    if run_type == MOCK_SERIES_SCALE:
        raise ProductionRepairableError(
            code=ProductionErrorCode.INVALID_RUN_TYPE,
            message="mock_series_scale must be started from the one-sentence mock scheduler entry.",
            cause="invalid_run_type",
            repair_action="Use /api/video-production/one-sentence with run_type=mock_series_scale.",
            repair_route="/one-sentence-video",
            retryable=True,
        )
    _assert_budget_allows_real_short_start(run_type, budget_limit)
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ProductionRepairableError(
            code=ProductionErrorCode.RUN_LINK_MISSING,
            message="Series not found.",
            repair_action="Open a valid series",
            affected_ids=[series_id],
        )
    if _style_lock(series).get("locked") is not True:
        raise ProductionRepairableError(
            code=ProductionErrorCode.STYLE_LOCK_MISSING,
            message="Series style is not locked.",
            repair_action="Lock style before production",
            repair_route=f"/series/{series_id}",
            retryable=True,
            affected_ids=[series_id],
        )

    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise ProductionRepairableError(
            code=ProductionErrorCode.RUN_LINK_MISSING,
            message="Episode not found.",
            repair_action="Open a valid episode",
            repair_route=f"/series/{series_id}",
            affected_ids=[episode_id],
        )
    storyboard = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {}
    if not storyboard.get("frames"):
        storyboard = _build_style_locked_storyboard(
            db,
            series=series,
            episode=episode,
            target_duration_seconds=target_duration_seconds,
        )
    effective_duration = target_duration_seconds or series.target_duration or episode.duration_seconds or _target_duration_from_storyboard(storyboard)
    _assert_real_short_duration(run_type, effective_duration)

    plan = create_episode_production_plan(
        db,
        series_id,
        episode_id,
        target_duration_seconds=target_duration_seconds,
        budget_limit=budget_limit,
    )
    production_episode = _production_episode_for_plan(db, plan.id, episode_id)
    ensure_shot_segments(db, production_episode.id)
    run = create_linked_run(db, series_id, episode_id, production_plan_id=plan.id, run_type=run_type)
    episode.status = "rendering"
    db.commit()
    db.refresh(episode)
    if auto_repair_policy is not None:
        trace = dict(run.model_trace_json or {})
        trace["auto_repair_policy"] = auto_repair_policy
        run.model_trace_json = trace
        db.commit()
        db.refresh(run)
    trace = dict(run.model_trace_json or {})
    trace["autopilot"] = {
        "enabled": bool(autostart_images),
        "source": "episode_start",
    }
    run.model_trace_json = trace
    db.commit()
    db.refresh(run)
    if autostart_images:
        run = await start_image_stage(db, run.id)
    return run
