"""导演工坊 API — 分镜编排 + 模型路由 + 音频策略."""
import asyncio
import json
import logging
import math
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Episode, Series
from app.services.ai_generator import ai_generator
from app.services.agency_orchestrator import AgencyOrchestrator
from app.services.ai_text_artifact_service import AITextArtifactService
from app.services.runtime_model_config import RuntimeModelConfigError, resolve_runtime_model_config
from app.services.video_agency_team import build_agency_context, ensure_video_agency_team

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/director", tags=["director"])

PREFERRED_SEEDANCE_SHOT_SECONDS = 8
MAX_CHARACTER_REFERENCE_IMAGES = 9
MAX_STYLE_REFERENCE_IMAGES = 3
SHOT_TYPE_SEQUENCE = ("wide", "medium", "close_up")
DIRECTOR_GENERATION_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_DIRECTOR_GENERATION_TIMEOUT_SECONDS", "12"))
DIRECTOR_AGENCY_REVIEW_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_DIRECTOR_AGENCY_REVIEW_TIMEOUT_SECONDS", "8"))


def _missing_agency_trace(stage: str, exc: Exception) -> dict:
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "EXPERT_MODEL_CONFIG_MISSING",
        "error_message": str(exc),
    }


def _timeout_trace(stage: str, error_code: str, timeout_seconds: float) -> dict:
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": error_code,
        "error_message": f"{stage} exceeded {timeout_seconds:g} seconds.",
    }


def _agency_trace_blocks(trace: dict | None) -> bool:
    return bool(isinstance(trace, dict) and trace.get("stage_status") in {"blocked", "failed"})


class DirectorScene(BaseModel):
    narration: str
    image_prompt: str
    shot_type: str = "medium"
    camera_angle: str = "eye_level"
    camera_movement: str = "static"
    composition: str = "rule_of_thirds"
    color_grade: str = "natural"
    lighting_mood: str = "natural"
    voice_id: Optional[str] = None
    reference_urls: Optional[list[str]] = None
    audio_mode: str = "tts"
    duration: float = 5.0


class DirectorPlanRequest(BaseModel):
    series_id: str
    episode_id: str
    scenes: list[DirectorScene]
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.3


class DirectorAutoPlanRequest(BaseModel):
    series_id: str
    episode_id: str
    target_duration: Optional[int] = None


class EpisodeProductionPlanRequest(BaseModel):
    series_id: str
    episode_id: str
    target_duration_seconds: Optional[int] = None
    target_duration: Optional[int] = None
    budget_limit: Optional[float] = None


class EpisodePlanRequest(EpisodeProductionPlanRequest):
    include_segments: bool = True


class ShotSegmentsRequest(BaseModel):
    production_episode_id: str
    preferred_segment_seconds: float = 8.0


def _parse_frames_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    import re
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    key_pos = raw.find('"frames"')
    if key_pos >= 0:
        start = raw.rfind('{', 0, key_pos)
        if start >= 0:
            depth = 0
            for i in range(start, len(raw)):
                if raw[i] == '{':
                    depth += 1
                elif raw[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[start:i + 1])
                        except json.JSONDecodeError:
                            break
    raise ValueError(f"Cannot parse director frames JSON: {raw[:300]}")


def _refs_by_id(items: list[dict]) -> dict[str, list[str]]:
    return {item.get("id"): item.get("reference_urls", []) for item in items if item.get("id")}


def _dedupe_refs(refs: list[str], limit: int | None = None) -> list[str]:
    deduped = list(dict.fromkeys([ref for ref in refs if ref]))
    return deduped[:limit] if limit else deduped


def _duration_chunks(duration: float) -> list[float]:
    safe_duration = max(1.0, float(duration or PREFERRED_SEEDANCE_SHOT_SECONDS))
    if safe_duration <= PREFERRED_SEEDANCE_SHOT_SECONDS:
        return [round(safe_duration, 2)]
    chunk_count = max(1, math.ceil(safe_duration / PREFERRED_SEEDANCE_SHOT_SECONDS))
    chunk = round(safe_duration / chunk_count, 2)
    chunks = [chunk for _ in range(chunk_count)]
    chunks[-1] = round(safe_duration - sum(chunks[:-1]), 2)
    return chunks


def _reference_instructions(character_refs: list[str], style_refs: list[str]) -> str:
    instructions = []
    if character_refs:
        instructions.append(
            "Use @Image 1 to lock character face, hairstyle, outfit, body proportions, and costume continuity across every shot."
        )
    if style_refs:
        start = len(character_refs) + 1
        end = start + len(style_refs) - 1
        label = f"@Image {start}" if start == end else f"@Image {start}-@Image {end}"
        instructions.append(
            f"Use {label} to lock the color palette, lighting mood, lens language, and environment style."
        )
    return " ".join(instructions)


def _prompt_with_style(frame_prompt: str, visual_style_prompt: str, reference_instructions: str) -> str:
    parts = [part for part in [frame_prompt] if part]
    if visual_style_prompt and visual_style_prompt not in frame_prompt:
        parts.append(f"Visual style: {visual_style_prompt}")
    if reference_instructions:
        parts.append(f"Reference anchors: {reference_instructions}")
    return "\n".join(parts)


def _continuity_notes(base_notes: str, reference_instructions: str, segment_index: int, segment_count: int) -> str:
    notes = [base_notes or "Follow the locked character and scene references exactly."]
    if reference_instructions:
        notes.append(reference_instructions)
    if segment_count > 1:
        notes.append(
            f"Segment {segment_index}/{segment_count}: continue the same action beat; use the previous segment end frame as continuity reference when available."
        )
    return " ".join(notes)


def _normalize_auto_frames(raw_frames: list[dict], style_lock: dict, target_duration: int) -> list[dict]:
    characters = style_lock.get("characters", [])
    scenes = style_lock.get("scenes", [])
    visual_style = style_lock.get("visual_style", {}) or {}
    visual_style_prompt = visual_style.get("prompt", "")
    visual_style_refs = _dedupe_refs(visual_style.get("reference_urls", []) or [], MAX_STYLE_REFERENCE_IMAGES)
    default_character_ids = [c["id"] for c in characters if c.get("id")]
    default_scene_id = scenes[0].get("id") if scenes else None
    char_refs = _refs_by_id(characters)
    scene_refs = _refs_by_id(scenes)
    frames = raw_frames or []
    if not frames:
        frames = [{
            "narration": "Introduce the episode conflict.",
            "image_prompt": style_lock.get("visual_style", {}).get("prompt", ""),
        }]

    default_duration = max(1, round(target_duration / max(len(frames), 1), 2))
    normalized = []
    for idx, frame in enumerate(frames):
        character_ids = frame.get("character_ids") or default_character_ids[:1]
        scene_id = frame.get("scene_id") or default_scene_id
        explicit_refs = list(frame.get("reference_urls") or [])
        character_reference_urls = []
        for cid in character_ids:
            character_reference_urls.extend(char_refs.get(cid, []))
        character_reference_urls = _dedupe_refs(character_reference_urls, MAX_CHARACTER_REFERENCE_IMAGES)
        style_reference_urls = _dedupe_refs(scene_refs.get(scene_id, []) + visual_style_refs, MAX_STYLE_REFERENCE_IMAGES)
        reference_urls = _dedupe_refs(explicit_refs + character_reference_urls + style_reference_urls)
        reference_instructions = _reference_instructions(character_reference_urls, style_reference_urls)
        frame_id = str(frame.get("frame_id") or f"frame-{idx + 1:03d}")
        frame_prompt = frame.get("image_prompt") or frame.get("visual_prompt") or ""
        base = {
            "index": idx,
            "frame_id": frame_id,
            "narration": frame.get("narration") or frame.get("voiceover") or "",
            "image_prompt": _prompt_with_style(frame_prompt, visual_style_prompt, reference_instructions),
            "video_prompt": frame.get("video_prompt") or frame.get("motion_prompt") or "",
            "duration": float(frame.get("duration") or default_duration),
            "audio_mode": frame.get("audio_mode") or "tts",
            "character_ids": character_ids,
            "scene_id": scene_id,
            "reference_urls": reference_urls,
            "character_reference_urls": character_reference_urls,
            "style_reference_urls": style_reference_urls,
            "reference_instructions": reference_instructions,
            "continuity_notes": frame.get("continuity_notes")
                or "Follow the locked character and scene references exactly.",
            "shot_type": frame.get("shot_type", "medium"),
            "camera_movement": frame.get("camera_movement", "static"),
            "action": frame.get("action") or frame.get("visual_action") or "",
            "emotion": frame.get("emotion") or frame.get("mood") or "",
        }
        chunks = _duration_chunks(base["duration"])
        for segment_index, chunk_duration in enumerate(chunks, start=1):
            shot = dict(base)
            shot["duration"] = chunk_duration
            shot["segment_index"] = segment_index
            shot["segment_count"] = len(chunks)
            shot["continuity_notes"] = _continuity_notes(
                base["continuity_notes"],
                reference_instructions,
                segment_index,
                len(chunks),
            )
            if len(chunks) > 1:
                shot["parent_frame_id"] = frame_id
                shot["frame_id"] = f"{frame_id}-shot-{segment_index:02d}"
                shot["shot_type"] = SHOT_TYPE_SEQUENCE[(segment_index - 1) % len(SHOT_TYPE_SEQUENCE)]
            normalized.append(shot)
    for index, frame in enumerate(normalized):
        frame["index"] = index
    return normalized


def _fallback_auto_plan_frames(series: Series, episode: Episode, style_lock: dict, target_duration: int) -> list[dict]:
    characters = style_lock.get("characters") or []
    scenes = style_lock.get("scenes") or []
    character_name = (characters[0] or {}).get("name") if characters else "the protagonist"
    scene_name = (scenes[0] or {}).get("name") if scenes else "the locked scene"
    beat_count = max(1, math.ceil(max(1, target_duration) / 30))
    duration = round(max(1, target_duration) / beat_count, 2)
    frames = []
    for index in range(beat_count):
        if index == 0:
            action = "establish the episode problem and daily context"
            shot_type = "wide"
        elif index == beat_count - 1:
            action = "summarize the practical takeaway and next action"
            shot_type = "close_up"
        else:
            action = "show the key habit adjustment with clear visual cause and effect"
            shot_type = "medium"
        frames.append({
            "frame_id": f"fallback-frame-{index + 1:03d}",
            "narration": f"{episode.title or 'This episode'} follows {character_name} in {scene_name}: {action}.",
            "image_prompt": (
                f"{series.logline or series.title}. {character_name} in {scene_name}, "
                f"{action}, realistic continuity, locked character and scene references."
            ),
            "duration": duration,
            "audio_mode": "tts",
            "action": action,
            "emotion": "calm and practical",
            "shot_type": shot_type,
            "continuity_notes": "Use the locked references and keep identity, wardrobe, lighting, and color consistent.",
        })
    return frames


def _storyboard_lines(storyboard: dict[str, Any], key: str) -> list[str]:
    frames = storyboard.get("frames") or []
    if not isinstance(frames, list):
        return []
    lines: list[str] = []
    for frame in frames:
        if isinstance(frame, dict) and frame.get(key):
            lines.append(str(frame[key]))
    return lines


def _record_director_storyboard_artifacts(
    db: Session,
    series: Series,
    episode: Episode,
    storyboard: dict[str, Any],
    prompt: dict[str, Any],
) -> None:
    service = AITextArtifactService(db)
    dialogue_lines = _storyboard_lines(storyboard, "narration")
    image_prompts = _storyboard_lines(storyboard, "image_prompt")
    specs = [
        ("storyboard", storyboard, "\n".join(dialogue_lines)),
        ("dialogue", {"lines": dialogue_lines}, "\n".join(dialogue_lines)),
        ("image_prompt", {"prompts": image_prompts}, "\n".join(image_prompts)),
    ]
    video_prompts = _storyboard_lines(storyboard, "video_prompt")
    specs.append(("video_prompt", {"prompts": video_prompts}, "\n".join(video_prompts)))
    for artifact_type, content_json, content_text in specs:
        artifact = service.create_artifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type=artifact_type,
            source_type="ai",
            input_json={
                "source": "director_auto_plan",
                "prompt": prompt,
            },
            content_json=content_json,
            content_text=content_text,
            model_trace_json={
                "source": "director_auto_plan",
                "generation_trace": storyboard.get("generation_trace") or {},
                "artifact_type": artifact_type,
            },
            review_trace_json=storyboard.get("agency_trace") if isinstance(storyboard.get("agency_trace"), dict) else {},
            created_by="director_auto_plan",
            commit=False,
        )
        service.approve_artifact(artifact.id, actor_user_id="director_auto_plan", commit=False)


async def generate_auto_storyboard(db: Session, body: DirectorAutoPlanRequest) -> dict:
    series = db.query(Series).filter(Series.id == body.series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    episode = db.query(Episode).filter(
        Episode.id == body.episode_id,
        Episode.series_id == body.series_id,
    ).first()
    if not episode:
        raise HTTPException(404, "Episode not found")

    story_bible = series.story_bible_json or {}
    style_lock = story_bible.get("style_lock", {})
    if not style_lock.get("locked"):
        raise HTTPException(400, "Series style must be locked before auto-planning")
    agency_team = ensure_video_agency_team(style_lock)
    agency_context = build_agency_context(style_lock)

    target_duration = body.target_duration or series.target_duration or 60
    prompt = {
        "series": {"title": series.title, "logline": series.logline, "genre": series.genre},
        "episode": {"number": episode.episode_number, "title": episode.title},
        "target_duration": target_duration,
        "style_lock": style_lock,
        "agency_team": agency_team,
        "agency_context": agency_context,
        "requirements": [
            "Return JSON only with key frames.",
            "Each frame should include narration, image_prompt, video_prompt, duration, audio_mode, character_ids, scene_id, action, emotion, and continuity_notes.",
            "For videos longer than one minute, plan multi-shot narrative beats with Scene, Character, Action, Emotion, and Duration; the system will decompose long beats into 5-8 second Seedance shots.",
            "Use only locked character IDs and scene IDs.",
            "Keep character identity, costume, lighting, color palette, and lens language stable across all shots.",
            "Apply the embedded expert team quality gates, especially short_video_editing_coach pacing and douyin_strategist hook retention.",
        ],
    }
    generation_trace = {"stage": "storyboard_generation", "stage_status": "complete"}
    try:
        raw = await asyncio.wait_for(
            ai_generator.generate_custom(
                db,
                "You are a short-video director. Create a concise storyboard that preserves locked character and scene continuity.",
                json.dumps(prompt, ensure_ascii=False),
                max_tokens=4096,
                temperature=0.7,
            ),
            timeout=DIRECTOR_GENERATION_TIMEOUT_SECONDS,
        )
        parsed = _parse_frames_json(raw)
    except asyncio.TimeoutError:
        parsed = {"frames": _fallback_auto_plan_frames(series, episode, style_lock, target_duration)}
        generation_trace = _timeout_trace(
            "storyboard_generation",
            "DIRECTOR_GENERATION_TIMEOUT",
            DIRECTOR_GENERATION_TIMEOUT_SECONDS,
        )
    except Exception as e:
        logger.warning("Director auto-plan failed: %s", e)
        raise HTTPException(500, f"Director auto-plan failed: {e}")

    frames = _normalize_auto_frames(parsed.get("frames", []), style_lock, target_duration)
    storyboard = {
        "series_id": series.id,
        "episode_id": episode.id,
        "style_lock_version": style_lock.get("version", 0),
        "agency_team_version": agency_team.get("version", ""),
        "frames": frames,
        "frame_count": len(frames),
        "total_duration": sum(f["duration"] for f in frames),
        "edit_packaging": style_lock.get("edit_packaging", {}),
        "quality_gates": agency_context.get("quality_gates", {}),
        "generation_trace": generation_trace,
    }
    try:
        runtime_config = resolve_runtime_model_config(db, "llm_agency_expert_review")
    except RuntimeModelConfigError as exc:
        storyboard["agency_trace"] = _missing_agency_trace("storyboard", exc)
    else:
        try:
            storyboard["agency_trace"] = await asyncio.wait_for(
                AgencyOrchestrator().run_storyboard_review(
                    db,
                    series_id=series.id,
                    episode_id=episode.id,
                    stage_context={"storyboard": storyboard, "style_lock": style_lock},
                    runtime_config=runtime_config,
                ),
                timeout=DIRECTOR_AGENCY_REVIEW_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            storyboard["agency_trace"] = _timeout_trace(
                "storyboard",
                "DIRECTOR_REVIEW_TIMEOUT",
                DIRECTOR_AGENCY_REVIEW_TIMEOUT_SECONDS,
            )
    if _agency_trace_blocks(storyboard.get("agency_trace")):
        raise HTTPException(
            409,
            {
                "message": "Storyboard expert review blocked auto-plan persistence.",
                "agency_trace": storyboard["agency_trace"],
            },
        )
    episode.storyboard_json = storyboard
    _record_director_storyboard_artifacts(db, series, episode, storyboard, prompt)
    db.commit()
    return storyboard


@router.post("/auto-plan")
async def auto_plan_episode(body: DirectorAutoPlanRequest,
                            db: Session = Depends(get_db),
                            user = Depends(verify_admin_token)):
    storyboard = await generate_auto_storyboard(db, body)
    return {"ok": True, "storyboard": storyboard}


@router.post("/episode-production-plan")
def create_episode_production_plan_endpoint(
    body: EpisodeProductionPlanRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    from app.services.production_plan_service import ensure_episode_production_plan

    try:
        plan = ensure_episode_production_plan(
            db,
            body.series_id,
            body.episode_id,
            target_duration_seconds=(
                body.target_duration_seconds
                if body.target_duration_seconds is not None
                else body.target_duration
            ),
            budget_limit=body.budget_limit,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        "ok": True,
        "plan": {
            "id": plan.id,
            "series_id": plan.series_id,
            "status": plan.status,
        },
    }


@router.post("/episode-plan")
def create_episode_plan_endpoint(
    body: EpisodePlanRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    from app.db_models import ProductionEpisode
    from app.services.production_plan_service import ensure_episode_production_plan, ensure_shot_segments

    try:
        plan = ensure_episode_production_plan(
            db,
            body.series_id,
            body.episode_id,
            target_duration_seconds=(
                body.target_duration_seconds
                if body.target_duration_seconds is not None
                else body.target_duration
            ),
            budget_limit=body.budget_limit,
            include_segments=body.include_segments,
        )
        production_episode = db.query(ProductionEpisode).filter(
            ProductionEpisode.plan_id == plan.id,
            ProductionEpisode.episode_id == body.episode_id,
        ).one()
        segments = ensure_shot_segments(db, production_episode.id) if body.include_segments else []
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        "ok": True,
        "plan": {
            "id": plan.id,
            "series_id": plan.series_id,
            "status": plan.status,
        },
        "production_episode_id": production_episode.id,
        "segment_count": len(segments),
    }


@router.post("/shot-segments")
def create_shot_segments_endpoint(
    body: ShotSegmentsRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    from app.services.production_plan_service import ensure_shot_segments

    try:
        segments = ensure_shot_segments(db, body.production_episode_id, body.preferred_segment_seconds)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        "ok": True,
        "segments": [
            {"id": item.id, "segment_id": item.segment_id, "version": item.version}
            for item in segments
        ],
        "segment_count": len(segments),
    }


@router.post("/plan")
async def build_plan(body: DirectorPlanRequest,
                     user = Depends(verify_admin_token)):
    """
    构建导演计划 (分镜表).
    自动为每帧选择最优模型路由.
    """
    frames = []
    for i, scene in enumerate(body.scenes):
        frames.append({
            "index": i,
            "narration": scene.narration,
            "image_prompt": scene.image_prompt,
            "shot_type": scene.shot_type,
            "camera_angle": scene.camera_angle,
            "camera_movement": scene.camera_movement,
            "composition": scene.composition,
            "color_grade": scene.color_grade,
            "lighting_mood": scene.lighting_mood,
            "voice_id": scene.voice_id,
            "reference_urls": scene.reference_urls,
            "audio_mode": scene.audio_mode,
            "duration": scene.duration,
        })

    total_duration = sum(f["duration"] for f in frames)
    return {
        "ok": True,
        "plan": {
            "series_id": body.series_id,
            "episode_id": body.episode_id,
            "frames": frames,
            "frame_count": len(frames),
            "total_duration": total_duration,
            "bgm_path": body.bgm_path,
            "bgm_volume": body.bgm_volume,
        }
    }
