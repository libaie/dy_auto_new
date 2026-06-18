from __future__ import annotations

import asyncio
import os
from math import ceil
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import bj_now
from app.db_models import Character, Episode, ProductionSegment, ProductionScene, ProductionShot, Scene, Series, VideoProductionRun
from app.services.agency_orchestrator import AgencyOrchestrator
from app.services import production_run_service
from app.services import production_plan_service
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.production_observability import record_production_event
from app.services import reference_asset_service
from app.services.reference_asset_service import ReferenceAssetError
from app.services.runtime_model_config import RuntimeModelConfigError, resolve_runtime_model_config
from app.services.video_agency_team import ensure_video_agency_team
from app.services.video_production_service import VideoProductionError
from app.services.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E, validate_run_type
from app.services.visual_style_inference_service import append_visual_style_constraints, infer_visual_style_from_story, merge_visual_style


DEFAULT_TARGET_SECONDS = 60
MAX_STORYBOARD_FRAME_SECONDS = 8
MIN_MULTI_SHOT_SECONDS = 15
MIN_MULTI_SHOT_FRAME_COUNT = 3
MAX_MATERIALIZED_STORYBOARD_FRAMES = 120
REAL_SHORT_MIN_SECONDS = 5
REAL_SHORT_MAX_SECONDS = 28800
CHARACTER_REFERENCE_FIELDS = (
    "avatar_front_url",
    "avatar_side_url",
    "avatar_threequarter_url",
    "avatar_fullbody_url",
)
SCENE_REFERENCE_FIELDS = (
    "reference_wideshot_url",
    "reference_midshot_url",
    "reference_aerial_url",
)
BLOCKING_AGENCY_STATUSES = {"blocked", "failed"}
ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS", "8"))
ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS", "8"))
ONE_SENTENCE_REFERENCE_RUNNING_STATUS = "reference_generation_running"
ONE_SENTENCE_REFERENCE_BLOCKED_STATUS = "reference_generation_blocked"


def _missing_agency_trace(stage: str, exc: Exception) -> dict[str, Any]:
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "EXPERT_MODEL_CONFIG_MISSING",
        "error_message": str(exc),
    }


def _timeout_trace(stage: str, error_code: str, timeout_seconds: float) -> dict[str, Any]:
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": error_code,
        "error_message": f"{stage} exceeded {timeout_seconds:g} seconds.",
    }


def _agency_trace_status(*traces: dict[str, Any] | None) -> str:
    return "complete" if traces and all(trace and not trace.get("error_code") for trace in traces) else "partial"


def _dedupe_urls(urls: list[str]) -> list[str]:
    return list(dict.fromkeys(url for url in urls if url))


def _reference_urls_from_fields(row: Any, fields: tuple[str, ...]) -> list[str]:
    return _dedupe_urls([
        value
        for field in fields
        if reference_asset_service.reference_url_is_usable(value := getattr(row, field, None))
    ])


def _reference_instruction(character_urls: list[str], style_urls: list[str]) -> str:
    parts = []
    if character_urls:
        parts.append(
            "@Image 1 locks the protagonist face, hairstyle, outfit, and body proportions; "
            "additional character images reinforce side, three-quarter, and full-body identity."
        )
    if style_urls:
        parts.append("Style reference images lock scene layout, lighting, palette, and mood.")
    return " ".join(parts)


def _agency_trace_blocks(trace: dict[str, Any] | None) -> bool:
    return bool(trace and trace.get("stage_status") in BLOCKING_AGENCY_STATUSES)


def _raise_blocked_agency_gate(
    db: Session,
    run: Any,
    *traces: dict[str, Any] | None,
) -> None:
    blocking_traces = [trace for trace in traces if _agency_trace_blocks(trace)]
    if not blocking_traces:
        return
    first = blocking_traces[0]
    invocation_ids = []
    for trace in blocking_traces:
        invocation_ids.extend([str(item) for item in (trace.get("invocation_ids") or []) if item])
    run.status = "blocked"
    run.current_stage = str(first.get("stage") or "expert_review")
    record_production_event(
        db,
        event_type="one_sentence.expert_gate_blocked",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        payload={
            "stage": first.get("stage"),
            "stage_status": first.get("stage_status"),
            "invocation_ids": invocation_ids,
        },
    )
    db.commit()
    raise ProductionRepairableError(
        code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
        message=f"{first.get('stage', 'expert')} expert review blocked one-sentence production.",
        cause="one_sentence_expert_gate_blocked",
        repair_action="Open the expert trace, fix required style/storyboard changes, then regenerate one-sentence production.",
        repair_route=f"/video-production/{run.id}",
        retryable=True,
        affected_ids=invocation_ids or [run.id],
    )


def _clean_prompt(prompt: str) -> str:
    return " ".join((prompt or "").strip().split())


def _title_from_prompt(prompt: str, explicit_title: str | None = None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()[:80]
    clean = _clean_prompt(prompt)
    return clean[:28] + ("..." if len(clean) > 28 else "")


def _segment_durations(total_seconds: int) -> list[int]:
    frame_count = max(1, ceil(total_seconds / MAX_STORYBOARD_FRAME_SECONDS))
    if total_seconds >= MIN_MULTI_SHOT_SECONDS:
        frame_count = max(MIN_MULTI_SHOT_FRAME_COUNT, frame_count)
    base = total_seconds // frame_count
    remainder = total_seconds % frame_count
    return [base + (1 if index < remainder else 0) for index in range(frame_count)]


def _shot_type(index: int, total: int) -> str:
    if total == 1:
        return "medium"
    sequence = ["wide", "medium", "close_up", "medium"]
    return sequence[index % len(sequence)]


def _scene_location_from_prompt(prompt: str) -> str:
    lowered = prompt.lower()
    details = []
    if "雨" in prompt or "rain" in lowered:
        details.append("rain-slick surfaces, visible raindrops, wet reflections")
    if "霓虹" in prompt or "neon" in lowered:
        details.append("neon signage and colored reflections")
    if "街" in prompt or "street" in lowered:
        details.append("urban street depth with foreground, midground, and background layers")
    if "剧场" in prompt or "theater" in lowered:
        details.append("abandoned theater interior with mirrors, stage depth, and practical light sources")
    if not details:
        details.append("a concrete story-specific environment with clear foreground action and background depth")
    return f"{'; '.join(details)}. Main story environment: {prompt}"


def _shot_beat(prompt: str, index: int, total: int) -> dict[str, str]:
    if total <= 1:
        return {
            "label": "core story moment",
            "image": f"Show the central story moment with immediate visual clarity: {prompt}",
            "video": f"Deliver the central action in one concise cinematic beat: {prompt}",
            "narration": prompt,
            "emotion": "focused",
        }
    if index == 0:
        return {
            "label": "opening hook",
            "image": f"Start with a strong visual hook from the central mystery; show the key object or conflict immediately: {prompt}",
            "video": f"Open fast on the mystery hook, then push the viewer toward the protagonist's discovery: {prompt}",
            "narration": "The clue appears before anyone is ready.",
            "emotion": "suspense",
        }
    if index == total - 1:
        return {
            "label": "close-up reveal and audience question",
            "image": f"End on a close-up reveal of the decisive clue or expression, leaving the mystery unresolved: {prompt}",
            "video": f"Close on the reveal and hold just long enough to invite the audience to wonder what happens next: {prompt}",
            "narration": "Who left this clue behind?",
            "emotion": "intrigued",
        }
    return {
        "label": "investigation beat",
        "image": f"Advance the action with the protagonist reacting to the clue and moving through the scene: {prompt}",
        "video": f"Show a clear action step that connects the hook to the final reveal: {prompt}",
        "narration": "One small detail pulls the story forward.",
        "emotion": "focused",
    }


def _build_style_lock(series: Series, character: Character, scene: Scene, prompt: str) -> dict[str, Any]:
    character_reference_urls = _reference_urls_from_fields(character, CHARACTER_REFERENCE_FIELDS)
    scene_reference_urls = _reference_urls_from_fields(scene, SCENE_REFERENCE_FIELDS)
    inferred_visual_style = infer_visual_style_from_story(
        prompt,
        series.title,
        series.logline,
        series.genre,
        character.appearance_desc,
        character.outfit_desc,
        scene.location_desc,
        scene.lighting,
        scene.mood,
    )
    visual_style = merge_visual_style(
        {
            "aspect_ratio": "9:16",
            "color_policy": "keep lighting and palette consistent across every shot",
            "reference_urls": scene_reference_urls[:3],
        },
        inferred_visual_style,
    )
    style_lock = {
            "locked": True,
            "version": 1,
            "source": "one_sentence",
            "series_id": series.id,
            "input_prompt": prompt,
            "visual_style": visual_style,
            "audio_packaging": {
                "voice_policy": "use project default TTS unless a character voice is configured",
                "bgm_policy": "restrained background music, low volume, do not overpower narration",
            },
            "edit_packaging": {
                "subtitle_style": "bottom safe-area subtitles with high contrast",
                "transition_style": "clean hard cuts between shots",
                "intro_outro": "none for the first automatic draft",
                "watermark": "",
            },
            "characters": [{
                "id": character.id,
                "name": character.name,
                "role_type": character.role_type,
                "appearance_desc": character.appearance_desc,
                "outfit_desc": character.outfit_desc,
                "reference_urls": character_reference_urls,
            }],
            "scenes": [{
                "id": scene.id,
                "name": scene.name,
                "scene_type": scene.scene_type,
                "location_desc": scene.location_desc,
                "lighting": scene.lighting,
                "mood": scene.mood,
                "reference_urls": scene_reference_urls,
            }],
            "style_anchors": [
                {"role": "style_reference", "url": url, "source": "scene_reference"}
                for url in scene_reference_urls[:3]
            ],
            "missing_assets": [],
    }
    ensure_video_agency_team(style_lock)
    return {"style_lock": style_lock}


def _without_agency_trace(value: dict[str, Any]) -> dict[str, Any]:
    clean = dict(value or {})
    clean.pop("agency_trace", None)
    return clean


def _first_linked_character_and_scene(db: Session, series: Series) -> tuple[Character | None, Scene | None]:
    character = series.characters[0] if series.characters else None
    scene = series.scenes[0] if series.scenes else None
    if character and scene:
        return character, scene
    character = db.query(Character).join(Series.characters).filter(Series.id == series.id).first()
    scene = db.query(Scene).join(Series.scenes).filter(Series.id == series.id).first()
    return character, scene


def _set_run_reference_generation_state(
    db: Session,
    run: VideoProductionRun,
    *,
    status: str,
    trace: dict[str, Any],
    autostart_images: bool,
) -> None:
    model_trace = dict(run.model_trace_json or {})
    one_sentence = dict(model_trace.get("one_sentence") or {})
    one_sentence["reference_generation"] = trace
    one_sentence["autostart_images_after_references"] = bool(autostart_images)
    model_trace["one_sentence"] = one_sentence
    run.model_trace_json = model_trace
    run.status = status
    run.current_stage = "reference_generation"
    run.updated_at = bj_now()
    db.commit()


def _mark_storyboard_ready_for_image_start(db: Session, run: VideoProductionRun) -> VideoProductionRun:
    run.status = "storyboard_ready"
    run.current_stage = "storyboard_ready"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run


def _is_past_one_sentence_reference_generation(run: VideoProductionRun) -> bool:
    return run.status not in {
        "draft",
        "storyboard_ready",
        ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
        ONE_SENTENCE_REFERENCE_BLOCKED_STATUS,
    }


def _storyboard_frames_by_id(storyboard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(frame.get("frame_id")): frame
        for frame in (storyboard.get("frames") or [])
        if isinstance(frame, dict) and frame.get("frame_id")
    }


def _refresh_segment_references_from_storyboard(
    db: Session,
    run: VideoProductionRun,
    storyboard: dict[str, Any],
    style_lock: dict[str, Any],
) -> None:
    if not run.production_episode_id:
        return
    frames = _storyboard_frames_by_id(storyboard)
    ordered_frames = [frame for frame in (storyboard.get("frames") or []) if isinstance(frame, dict)]
    if not frames and not ordered_frames:
        return
    rows = (
        db.query(ProductionSegment, ProductionShot)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .filter(ProductionShot.scene_plan_id.in_(
            db.query(ProductionScene.id)
            .filter(ProductionScene.episode_plan_id == run.production_episode_id)
        ))
        .order_by(ProductionShot.order_index.asc(), ProductionSegment.order_index.asc())
        .all()
    )
    for segment, shot in rows:
        frame = frames.get(str(shot.shot_id))
        if not frame and ordered_frames:
            frame_index = max(0, int(shot.order_index or 1) - 1)
            frame = ordered_frames[min(frame_index, len(ordered_frames) - 1)]
        if not frame:
            continue
        segment.reference_roles_json = production_plan_service._reference_roles(frame, style_lock)
        flag_modified(segment, "reference_roles_json")
        segment.image_prompt = str(frame.get("image_prompt") or segment.image_prompt or "")
        segment.video_prompt = str(frame.get("video_prompt") or segment.video_prompt or "")
        segment.narration = frame.get("narration") or segment.narration
    db.commit()


async def _run_one_sentence_expert_reviews(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    run: VideoProductionRun,
    story_bible: dict[str, Any],
    storyboard: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        runtime_config = resolve_runtime_model_config(db, "llm_agency_expert_review")
    except RuntimeModelConfigError as exc:
        return _missing_agency_trace("style_lock", exc), _missing_agency_trace("storyboard", exc)

    orchestrator = AgencyOrchestrator()
    try:
        style_trace = await asyncio.wait_for(
            orchestrator.run_style_lock_review(
                db,
                series_id=series.id,
                run_id=run.id,
                production_plan_id=run.production_plan_id,
                production_episode_id=run.production_episode_id,
                stage_context={"style_lock": _without_agency_trace(story_bible.get("style_lock", {}))},
                runtime_config=runtime_config,
            ),
            timeout=ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        style_trace = _timeout_trace(
            "style_lock",
            "ONE_SENTENCE_STYLE_REVIEW_TIMEOUT",
            ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS,
        )
    try:
        storyboard_trace = await asyncio.wait_for(
            orchestrator.run_storyboard_review(
                db,
                series_id=series.id,
                episode_id=episode.id,
                run_id=run.id,
                production_plan_id=run.production_plan_id,
                production_episode_id=run.production_episode_id,
                stage_context={
                    "storyboard": _without_agency_trace(storyboard),
                    "style_lock": _without_agency_trace(story_bible.get("style_lock", {})),
                },
                runtime_config=runtime_config,
            ),
            timeout=ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        storyboard_trace = _timeout_trace(
            "storyboard",
            "ONE_SENTENCE_STORYBOARD_REVIEW_TIMEOUT",
            ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS,
        )
    return style_trace, storyboard_trace


def _build_storyboard(
    *,
    series: Series,
    episode: Episode,
    character: Character,
    scene: Scene,
    prompt: str,
    target_duration_seconds: int,
) -> dict[str, Any]:
    durations = _segment_durations(target_duration_seconds)
    total_frame_count = len(durations)
    materialized_durations = durations[:MAX_MATERIALIZED_STORYBOARD_FRAMES]
    character_reference_urls = _reference_urls_from_fields(character, CHARACTER_REFERENCE_FIELDS)[:9]
    style_reference_urls = _reference_urls_from_fields(scene, SCENE_REFERENCE_FIELDS)[:3]
    reference_urls = _dedupe_urls(character_reference_urls + style_reference_urls)
    reference_instructions = _reference_instruction(character_reference_urls, style_reference_urls)
    visual_style = series.story_bible_json.get("style_lock", {}).get("visual_style", {})
    frames = []
    for index, duration in enumerate(materialized_durations):
        shot_number = index + 1
        beat = _shot_beat(prompt, index, total_frame_count)
        frames.append({
            "frame_id": f"shot-{shot_number:03d}",
            "scene_id": scene.id,
            "character_ids": [character.id],
            "reference_urls": reference_urls,
            "character_reference_urls": character_reference_urls,
            "style_reference_urls": style_reference_urls,
            "reference_instructions": reference_instructions,
            "image_prompt": append_visual_style_constraints(
                (
                    f"{reference_instructions} Vertical cinematic frame. {beat['image']}. "
                    f"Shot {shot_number}, {_shot_type(index, total_frame_count)} shot, "
                    "stable protagonist identity, consistent lighting, no text, no logo, no watermark."
                ),
                visual_style,
            ),
            "video_prompt": (
                f"{reference_instructions} {beat['video']}. "
                f"Shot {shot_number}, {_shot_type(index, total_frame_count)} shot, "
                f"{visual_style.get('prompt', '')}. smooth camera movement, coherent action, stable face and outfit, no text. "
                f"{visual_style.get('negative_prompt', '')}"
            ),
            "narration": beat["narration"],
            "duration": duration,
            "audio_mode": "tts",
            "bgm_direction": "restrained suspense bed with rain ambience and a small rise on the final reveal",
            "continuity_notes": (
                "Maintain the same protagonist appearance, costume, environment lighting, "
                "and emotional tone from previous shots."
            ),
            "action": beat["label"],
            "emotion": beat["emotion"],
            "shot_type": _shot_type(index, total_frame_count),
        })
    materialized_duration = sum(materialized_durations)
    remaining_frame_count = max(0, total_frame_count - len(frames))
    remaining_duration = max(0, target_duration_seconds - materialized_duration)
    return {
        "series_id": series.id,
        "episode_id": episode.id,
        "style_lock_version": 1,
        "source": "one_sentence",
        "frames": frames,
        "frame_count": total_frame_count,
        "materialized_frame_count": len(frames),
        "materialized_duration": materialized_duration,
        "total_duration": target_duration_seconds,
        "storyboard_window": {
            "mode": "windowed" if remaining_frame_count else "complete",
            "window_index": 1,
            "max_materialized_frames": MAX_MATERIALIZED_STORYBOARD_FRAMES,
            "start_frame_index": 1,
            "end_frame_index": len(frames),
            "remaining_frame_count": remaining_frame_count,
            "remaining_duration": remaining_duration,
        },
        "edit_packaging": series.story_bible_json.get("style_lock", {}).get("edit_packaging", {}),
    }


def _steps(run_status: str, autostart_images: bool, frame_count: int) -> list[dict[str, Any]]:
    if run_status == ONE_SENTENCE_REFERENCE_RUNNING_STATUS:
        return [
            {"key": "prompt", "label": "提示词已接收", "status": "done"},
            {"key": "series", "label": "系列与剧集已创建", "status": "done"},
            {"key": "reference_generation", "label": "参考图生成", "status": "running"},
            {"key": "style_lock", "label": "风格锁定", "status": "waiting"},
            {"key": "storyboard", "label": "分镜生成", "status": "waiting", "frame_count": frame_count},
            {"key": "production_plan", "label": "生产计划关联", "status": "waiting"},
            {"key": "image_generation", "label": "画面生成", "status": "waiting"},
            {"key": "image_review", "label": "画面审查闸门", "status": "waiting"},
            {"key": "video_generation", "label": "视频片段生成", "status": "waiting"},
            {"key": "video_review", "label": "视频审查闸门", "status": "waiting"},
            {"key": "compose", "label": "最终合成", "status": "waiting"},
            {"key": "final_review", "label": "最终审查闸门", "status": "waiting"},
            {"key": "completed", "label": "成片完成", "status": "waiting"},
        ]
    image_status = "running" if autostart_images and run_status == "image_batch_running" else "ready"
    return [
        {"key": "prompt", "label": "提示词已接收", "status": "done"},
        {"key": "series", "label": "系列与剧集已创建", "status": "done"},
        {"key": "style_lock", "label": "风格已锁定", "status": "done"},
        {"key": "storyboard", "label": "分镜已生成", "status": "done", "frame_count": frame_count},
        {"key": "production_plan", "label": "生产计划已关联", "status": "done"},
        {"key": "image_generation", "label": "画面生成", "status": image_status},
        {"key": "image_review", "label": "画面审查闸门", "status": "pending"},
        {"key": "video_generation", "label": "视频片段生成", "status": "waiting"},
        {"key": "video_review", "label": "视频审查闸门", "status": "waiting"},
        {"key": "compose", "label": "最终合成", "status": "waiting"},
        {"key": "final_review", "label": "最终审查闸门", "status": "waiting"},
        {"key": "completed", "label": "成片完成", "status": "waiting"},
    ]


def _invalid_run_type(run_type: str, message: str) -> ProductionRepairableError:
    return ProductionRepairableError(
        code=ProductionErrorCode.INVALID_RUN_TYPE,
        message=message,
        cause="invalid_run_type",
        repair_action="Use run_type=real_short_e2e for one-sentence real short runs.",
        repair_route="/video-production",
        affected_ids=[run_type],
    )


def _validate_one_sentence_run_type(run_type: str | None) -> str:
    try:
        validated = validate_run_type(run_type or REAL_SHORT_E2E)
    except ValueError as exc:
        raise _invalid_run_type(str(run_type), str(exc)) from exc
    return validated


def _validate_real_short_duration(run_type: str, target_duration_seconds: int) -> None:
    if run_type != REAL_SHORT_E2E:
        return
    if not REAL_SHORT_MIN_SECONDS <= target_duration_seconds <= REAL_SHORT_MAX_SECONDS:
        raise VideoProductionError(
            f"real_short_e2e target_duration_seconds must be at least {REAL_SHORT_MIN_SECONDS} seconds "
            f"and no more than {REAL_SHORT_MAX_SECONDS} seconds."
        )


def _assert_budget_allows_real_short(run_type: str, budget_limit: float | None) -> None:
    if run_type == REAL_SHORT_E2E and (budget_limit is None or float(budget_limit) <= 0):
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_EXCEEDED,
            message="real_short_e2e requires a positive budget_limit before production can start.",
            cause="budget_limit_exhausted",
            repair_action="Set budget_limit greater than 0 or use mock_series_scale for provider-free runs.",
            repair_route="/video-production",
            retryable=True,
        )


async def _generate_required_reference_images(db: Session, character: Character, scene: Scene) -> None:
    await reference_asset_service.generate_character_reference_images(db, character.id, slot="all")
    await reference_asset_service.generate_scene_reference_images(db, scene.id, slot="all")


async def _generate_required_references(db: Session, character: Character, scene: Scene) -> dict[str, Any]:
    try:
        await asyncio.wait_for(
            _generate_required_reference_images(db, character, scene),
            timeout=ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        db.refresh(character)
        db.refresh(scene)
        return _timeout_trace(
            "reference_generation",
            "REFERENCE_GENERATION_TIMEOUT",
            ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS,
        )
    except ReferenceAssetError as exc:
        raise ProductionRepairableError(
            code=ProductionErrorCode.ASSET_URL_MISSING,
            message=f"Required one-sentence reference images are missing: {exc.message}",
            cause=exc.code,
            repair_action="Configure a text-to-image model and regenerate character/scene reference images before starting production.",
            repair_route="/ai-models",
            retryable=True,
            affected_ids=[character.id, scene.id],
        ) from exc
    db.refresh(character)
    db.refresh(scene)
    missing = []
    if not _reference_urls_from_fields(character, CHARACTER_REFERENCE_FIELDS):
        missing.append(character.id)
    if not _reference_urls_from_fields(scene, SCENE_REFERENCE_FIELDS):
        missing.append(scene.id)
    if missing:
        raise ProductionRepairableError(
            code=ProductionErrorCode.ASSET_URL_MISSING,
            message="Required one-sentence reference images were not generated.",
            cause="reference_assets_empty",
            repair_action="Regenerate character and scene reference images, then retry one-sentence production.",
            repair_route="/reference-assets",
            retryable=True,
            affected_ids=missing,
        )
    return {"stage": "reference_generation", "stage_status": "complete"}


async def complete_one_sentence_reference_generation(
    db: Session,
    run_id: str,
    *,
    autostart_images: bool | None = None,
) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    series = db.query(Series).filter(Series.id == run.series_id).first()
    episode = db.query(Episode).filter(Episode.id == run.episode_id).first()
    if not series or not episode:
        raise VideoProductionError("Run series or episode not found")
    character, scene = _first_linked_character_and_scene(db, series)
    if not character or not scene:
        raise VideoProductionError("Run is missing linked character or scene")
    if _is_past_one_sentence_reference_generation(run):
        return run

    trace = dict((run.model_trace_json or {}).get("one_sentence") or {})
    should_autostart = bool(
        autostart_images
        if autostart_images is not None
        else trace.get("autostart_images_after_references")
    )
    _set_run_reference_generation_state(
        db,
        run,
        status=ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
        trace={"stage": "reference_generation", "stage_status": "running"},
        autostart_images=should_autostart,
    )
    try:
        await _generate_required_reference_images(db, character, scene)
        db.refresh(character)
        db.refresh(scene)
        if not _reference_urls_from_fields(character, CHARACTER_REFERENCE_FIELDS) or not _reference_urls_from_fields(scene, SCENE_REFERENCE_FIELDS):
            raise VideoProductionError("Reference generation completed without usable character and scene URLs")

        story_bible = _build_style_lock(series, character, scene, series.logline or series.title)
        story_bible["style_lock"]["reference_generation_trace"] = {
            "stage": "reference_generation",
            "stage_status": "complete",
        }
        series.story_bible_json = story_bible
        storyboard = _build_storyboard(
            series=series,
            episode=episode,
            character=character,
            scene=scene,
            prompt=series.logline or series.title,
            target_duration_seconds=int(series.target_duration or episode.duration_seconds or DEFAULT_TARGET_SECONDS),
        )
        episode.storyboard_json = storyboard
        run.storyboard_json = storyboard
        flag_modified(series, "story_bible_json")
        flag_modified(episode, "storyboard_json")
        flag_modified(run, "storyboard_json")
        db.commit()
        db.refresh(series)
        db.refresh(episode)
        db.refresh(run)

        _refresh_segment_references_from_storyboard(db, run, storyboard, story_bible["style_lock"])
        style_trace, storyboard_trace = await _run_one_sentence_expert_reviews(
            db,
            series=series,
            episode=episode,
            run=run,
            story_bible=story_bible,
            storyboard=storyboard,
        )
        story_bible["style_lock"]["agency_trace"] = style_trace
        storyboard["agency_trace"] = storyboard_trace
        series.story_bible_json = {**story_bible, "style_lock": dict(story_bible["style_lock"])}
        episode.storyboard_json = dict(storyboard)
        run.storyboard_json = dict(storyboard)
        flag_modified(series, "story_bible_json")
        flag_modified(episode, "storyboard_json")
        flag_modified(run, "storyboard_json")
        db.commit()
        _raise_blocked_agency_gate(db, run, style_trace, storyboard_trace)

        if should_autostart:
            run = _mark_storyboard_ready_for_image_start(db, run)
            run = await production_run_service.start_image_stage(db, run.id)
        else:
            run = _mark_storyboard_ready_for_image_start(db, run)
        return run
    except Exception as exc:
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
        if run:
            if _is_past_one_sentence_reference_generation(run):
                return run
            error_trace = {
                "stage": "reference_generation",
                "stage_status": "failed",
                "error_code": exc.__class__.__name__,
                "error_message": str(exc),
            }
            model_trace = dict(run.model_trace_json or {})
            one_sentence = dict(model_trace.get("one_sentence") or {})
            one_sentence["reference_generation"] = error_trace
            model_trace["one_sentence"] = one_sentence
            run.model_trace_json = model_trace
            run.status = ONE_SENTENCE_REFERENCE_BLOCKED_STATUS
            run.current_stage = "reference_generation"
            run.error_message = str(exc)
            run.updated_at = bj_now()
            db.commit()
        raise


async def create_one_sentence_video(
    db: Session,
    *,
    prompt: str,
    title: str | None = None,
    genre: str = "drama",
    target_duration_seconds: int = DEFAULT_TARGET_SECONDS,
    budget_limit: float | None = None,
    autostart_images: bool = True,
    run_type: str | None = REAL_SHORT_E2E,
    auto_repair_policy: dict | None = None,
) -> dict[str, Any]:
    run_type = _validate_one_sentence_run_type(run_type)
    clean_prompt = _clean_prompt(prompt)
    title_value = _title_from_prompt(clean_prompt, title)
    target_duration_seconds = max(5, int(target_duration_seconds or DEFAULT_TARGET_SECONDS))
    _assert_budget_allows_real_short(run_type, budget_limit)
    if run_type == MOCK_SERIES_SCALE:
        from app.services.mock_scale_scheduler_service import create_mock_scale_run

        result = create_mock_scale_run(
            db,
            prompt=clean_prompt,
            title=title_value,
            target_duration_seconds=target_duration_seconds,
            budget_limit=budget_limit,
        )
        return {
            "series": result["series"],
            "episode": result["episode"],
            "run": result["run"],
            "steps": [
                {"key": "prompt", "label": "提示词已接收", "status": "done"},
                {"key": "production_plan", "label": "模拟生产计划已关联", "status": "done"},
                {"key": "mock_scheduler", "label": "模拟调度器", "status": "pending"},
                {"key": "completed", "label": "模拟运行完成", "status": "waiting"},
            ],
            "agency_trace_status": "complete",
            "agency_trace": {
                "mock_scheduler": {
                    "stage": "mock_scheduler",
                    "stage_status": "complete",
                    "provider_free": True,
                    "provider_calls": 0,
                }
            },
        }
    _validate_real_short_duration(run_type, target_duration_seconds)

    series = Series(
        title=title_value,
        logline=clean_prompt,
        genre=genre or "drama",
        total_episodes=1,
        target_duration=target_duration_seconds,
        mode="fully_automatic",
        pilot_first=True,
        status="rendering",
    )
    db.add(series)
    db.flush()

    character = Character(
        name="Main Character",
        role_type="protagonist",
        gender="unknown",
        age_range="adult",
        personality="Driven by the central conflict in the prompt.",
        appearance_desc=(
            "Adult protagonist with a clear recognizable face, stable hairstyle, natural proportions, "
            f"focused expression, and visual details inspired by the story prompt: {clean_prompt}"
        ),
        outfit_desc=(
            "Consistent fitted dark outer coat, neutral inner layer, practical trousers, and one subtle "
            "accent color carried across every shot."
        ),
    )
    scene = Scene(
        name="Primary Scene",
        scene_type="mixed",
        location_desc=_scene_location_from_prompt(clean_prompt),
        lighting="cinematic",
        mood="dramatic",
    )
    db.add(character)
    db.add(scene)
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    reference_trace = await _generate_required_references(db, character, scene)
    story_bible = _build_style_lock(series, character, scene, clean_prompt)
    story_bible["style_lock"]["reference_generation_trace"] = reference_trace
    series.story_bible_json = story_bible

    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Episode 1",
        status="storyboard_ready",
    )
    db.add(episode)
    db.flush()
    storyboard = _build_storyboard(
        series=series,
        episode=episode,
        character=character,
        scene=scene,
        prompt=clean_prompt,
        target_duration_seconds=target_duration_seconds,
    )
    episode.storyboard_json = storyboard

    run = await production_run_service.start_episode_production(
        db,
        series_id=series.id,
        episode_id=episode.id,
        target_duration_seconds=target_duration_seconds,
        budget_limit=budget_limit,
        autostart_images=False,
        run_type=run_type,
        auto_repair_policy=auto_repair_policy,
    )
    reference_pending = reference_trace.get("error_code") == "REFERENCE_GENERATION_TIMEOUT"
    if reference_pending:
        story_bible["style_lock"]["agency_trace"] = _timeout_trace(
            "style_lock",
            "ONE_SENTENCE_REFERENCE_GENERATION_PENDING",
            ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS,
        )
        storyboard["agency_trace"] = _timeout_trace(
            "storyboard",
            "ONE_SENTENCE_REFERENCE_GENERATION_PENDING",
            ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS,
        )
        series.story_bible_json = {**story_bible, "style_lock": dict(story_bible["style_lock"])}
        episode.storyboard_json = dict(storyboard)
        run.storyboard_json = dict(storyboard)
        flag_modified(series, "story_bible_json")
        flag_modified(episode, "storyboard_json")
        flag_modified(run, "storyboard_json")
        db.commit()
        _set_run_reference_generation_state(
            db,
            run,
            status=ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
            trace=reference_trace,
            autostart_images=autostart_images,
        )
        db.refresh(series)
        db.refresh(episode)
        db.refresh(run)
        record_production_event(
            db,
            event_type="one_sentence.reference_generation_deferred",
            run_id=run.id,
            production_plan_id=run.production_plan_id,
            production_episode_id=run.production_episode_id,
            payload={
                "series_id": series.id,
                "episode_id": episode.id,
                "target_duration_seconds": target_duration_seconds,
                "autostart_images": autostart_images,
                "run_type": run_type,
            },
        )
        return {
            "series": series,
            "episode": episode,
            "run": run,
            "steps": _steps(run.status, autostart_images, episode.storyboard_json.get("frame_count", 0)),
            "agency_trace_status": "partial",
            "agency_trace": {
                "style_lock": story_bible["style_lock"]["agency_trace"],
                "storyboard": storyboard["agency_trace"],
            },
            "background_reference_pending": True,
        }

    style_trace, storyboard_trace = await _run_one_sentence_expert_reviews(
        db,
        series=series,
        episode=episode,
        run=run,
        story_bible=story_bible,
        storyboard=storyboard,
    )
    story_bible["style_lock"]["agency_trace"] = style_trace
    storyboard["agency_trace"] = storyboard_trace
    series.story_bible_json = {
        **story_bible,
        "style_lock": dict(story_bible["style_lock"]),
    }
    episode.storyboard_json = dict(storyboard)
    flag_modified(series, "story_bible_json")
    flag_modified(episode, "storyboard_json")
    db.commit()
    db.refresh(series)
    db.refresh(episode)
    _raise_blocked_agency_gate(db, run, style_trace, storyboard_trace)

    if autostart_images:
        trace = dict(run.model_trace_json or {})
        trace["autopilot"] = {
            "enabled": True,
            "source": "one_sentence",
        }
        run.model_trace_json = trace
        db.commit()
        db.refresh(run)
        run = _mark_storyboard_ready_for_image_start(db, run)
        run = await production_run_service.start_image_stage(db, run.id)
    if not autostart_images and run.status == "draft":
        run = _mark_storyboard_ready_for_image_start(db, run)
    record_production_event(
        db,
        event_type="one_sentence.created",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        payload={
            "series_id": series.id,
            "episode_id": episode.id,
            "target_duration_seconds": target_duration_seconds,
            "autostart_images": autostart_images,
            "run_type": run_type,
        },
    )
    db.commit()
    db.refresh(run)
    return {
        "series": series,
        "episode": episode,
        "run": run,
        "steps": _steps(run.status, autostart_images, episode.storyboard_json.get("frame_count", 0)),
        "agency_trace_status": _agency_trace_status(style_trace, storyboard_trace),
        "agency_trace": {
            "style_lock": style_trace,
            "storyboard": storyboard_trace,
        },
        "background_reference_pending": False,
    }
