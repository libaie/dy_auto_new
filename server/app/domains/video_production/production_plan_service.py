from math import ceil
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.video_production import (
    ProductionEpisode,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
)
from app.db.models import (
    Episode,
    Series,
)
from app.domains.video_production.production_status import (
    CONTINUITY_CONTINUOUS_ACTION,
    CONTINUITY_NARRATIVE_CUT,
    PLAN_READY,
    REFERENCE_CHARACTER_ANCHOR,
    REFERENCE_STYLE_ANCHOR,
    SEGMENT_PLANNED,
)

MAX_SEGMENT_SECONDS = 8.0
DEFAULT_FRAME_SECONDS = 5.0


def _style_lock(series: Series) -> dict[str, Any]:
    story_bible = series.story_bible_json if isinstance(series.story_bible_json, dict) else {}
    style_lock = story_bible.get("style_lock") or {}
    return style_lock if isinstance(style_lock, dict) else {}


def _frames(episode: Episode) -> list[dict[str, Any]]:
    storyboard = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {}
    frames = storyboard.get("frames") or []
    if not isinstance(frames, list):
        raise ValueError("Episode storyboard_json frames must be a list")
    if any(not isinstance(frame, dict) for frame in frames):
        raise ValueError("Episode storyboard_json frames must contain objects")
    return frames


def _style_lock_version(style_lock: dict[str, Any]) -> int:
    try:
        return int(style_lock.get("version") or 1)
    except (TypeError, ValueError):
        return 1


def _frame_duration(frame: dict[str, Any]) -> float:
    try:
        duration = float(frame.get("duration") or frame.get("duration_seconds") or DEFAULT_FRAME_SECONDS)
    except (TypeError, ValueError):
        duration = DEFAULT_FRAME_SECONDS
    return duration if duration > 0 else DEFAULT_FRAME_SECONDS


def _segment_durations(duration: float, max_seconds: float = MAX_SEGMENT_SECONDS) -> list[float]:
    count = max(1, ceil(duration / max_seconds))
    each = round(duration / count, 2)
    values = [each for _ in range(count)]
    values[-1] = round(duration - sum(values[:-1]), 2)
    return values


def _extract_urls(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        urls = []
        for key in ("url", "reference_url", "image_url", "src"):
            if value.get(key):
                urls.append(str(value[key]))
        if value.get("reference_urls"):
            urls.extend(_extract_urls(value["reference_urls"]))
        return urls
    if isinstance(value, list):
        urls = []
        for item in value:
            urls.extend(_extract_urls(item))
        return urls
    return []


def _dedupe_urls(urls: list[str]) -> list[str]:
    return list(dict.fromkeys(url for url in urls if url))


def _style_reference_urls(style_lock: dict[str, Any]) -> list[str]:
    visual_style = style_lock.get("visual_style") or {}
    if not isinstance(visual_style, dict):
        visual_style = {}
    return _dedupe_urls(
        _extract_urls(style_lock.get("style_anchors"))
        + _extract_urls(visual_style.get("reference_urls"))
    )


def _reference_roles(frame: dict[str, Any], style_lock: dict[str, Any]) -> list[dict[str, Any]]:
    roles = []
    priority = 1
    for url in _dedupe_urls(_extract_urls(frame.get("reference_urls"))):
        roles.append({"role": REFERENCE_CHARACTER_ANCHOR, "url": url, "priority": priority})
        priority += 1
    for url in _style_reference_urls(style_lock):
        roles.append({"role": REFERENCE_STYLE_ANCHOR, "url": url, "priority": priority})
        priority += 1
    return roles


def _frame_continuity_mode(frame: dict[str, Any], segment_count: int) -> str:
    if segment_count > 1:
        return CONTINUITY_CONTINUOUS_ACTION
    return str(frame.get("continuity_mode") or CONTINUITY_NARRATIVE_CUT)


def create_episode_production_plan(
    db: Session,
    series_id: str,
    episode_id: str,
    target_duration_seconds: int | None = None,
    budget_limit: float | None = None,
    include_segments: bool = True,
) -> ProductionPlan:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("Series not found")

    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.series_id == series_id,
    ).first()
    if not episode:
        raise ValueError("Episode not found")

    style_lock = _style_lock(series)
    if style_lock.get("locked") is not True:
        raise ValueError("Series style must be locked before production planning")

    frames = _frames(episode)
    if not frames:
        raise ValueError("Episode storyboard_json is empty")

    target_duration = int(round(
        target_duration_seconds
        if target_duration_seconds is not None
        else sum(_frame_duration(frame) for frame in frames)
    ))
    version = _style_lock_version(style_lock)

    plan = ProductionPlan(
        series_id=series.id,
        status=PLAN_READY,
        active_version=version,
        target_total_duration_seconds=target_duration,
        budget_limit=budget_limit,
        current_cost=0.0,
    )
    db.add(plan)
    db.flush()

    db.add(ProductionPlanVersion(
        plan_id=plan.id,
        version=version,
        style_lock_json=style_lock,
        model_config_snapshot_json={},
        prompt_policy_json={
            "max_segment_seconds": MAX_SEGMENT_SECONDS,
            "reference_roles": [REFERENCE_CHARACTER_ANCHOR, REFERENCE_STYLE_ANCHOR],
        },
    ))

    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=episode.episode_number,
        status=PLAN_READY,
        target_duration_seconds=target_duration,
    )
    db.add(production_episode)
    db.flush()

    scenes_by_key: dict[str, ProductionScene] = {}
    for frame_index, frame in enumerate(frames, start=1):
        scene_key = str(frame.get("scene_id") or "scene-default")
        scene = scenes_by_key.get(scene_key)
        if scene is None:
            scene = ProductionScene(
                episode_plan_id=production_episode.id,
                scene_id=scene_key,
                order_index=len(scenes_by_key) + 1,
                status=PLAN_READY,
                location_summary=str(frame.get("scene_summary") or frame.get("location_summary") or scene_key),
            )
            db.add(scene)
            db.flush()
            scenes_by_key[scene_key] = scene

        frame_duration = _frame_duration(frame)
        shot_id = str(frame.get("frame_id") or frame.get("shot_id") or f"shot-{frame_index:03d}")
        shot = ProductionShot(
            scene_plan_id=scene.id,
            shot_id=shot_id,
            order_index=frame_index,
            status=PLAN_READY,
            character_ids=frame.get("character_ids") or [],
            action=str(frame.get("action") or frame.get("video_prompt") or ""),
            emotion=str(frame.get("emotion") or ""),
            shot_type=str(frame.get("shot_type") or "medium"),
            duration_seconds=frame_duration,
        )
        db.add(shot)
        db.flush()

        if include_segments:
            segment_durations = _segment_durations(frame_duration)
            continuity_mode = _frame_continuity_mode(frame, len(segment_durations))
            previous_segment: ProductionSegment | None = None
            for segment_index, segment_duration in enumerate(segment_durations, start=1):
                segment = ProductionSegment(
                    shot_plan_id=shot.id,
                    previous_segment_id=previous_segment.id if previous_segment else None,
                    segment_id=f"{shot_id}-seg-{segment_index:02d}",
                    order_index=segment_index,
                    status=SEGMENT_PLANNED,
                    duration_seconds=segment_duration,
                    continuity_mode=continuity_mode,
                    version=1,
                    expected_end_state=str(frame.get("expected_end_state") or ""),
                    image_prompt=str(frame.get("image_prompt") or frame.get("visual_prompt") or ""),
                    video_prompt=str(frame.get("video_prompt") or frame.get("action") or ""),
                    narration=frame.get("narration") or frame.get("voiceover"),
                    reference_roles_json=_reference_roles(frame, style_lock),
                )
                db.add(segment)
                db.flush()
                previous_segment = segment

    db.commit()
    db.refresh(plan)
    return plan


def ensure_episode_production_plan(
    db: Session,
    series_id: str,
    episode_id: str,
    target_duration_seconds: int | None = None,
    budget_limit: float | None = None,
    include_segments: bool = True,
) -> ProductionPlan:
    existing = (
        db.query(ProductionPlan)
        .join(ProductionEpisode, ProductionEpisode.plan_id == ProductionPlan.id)
        .filter(ProductionPlan.series_id == series_id, ProductionEpisode.episode_id == episode_id)
        .order_by(ProductionPlan.updated_at.desc(), ProductionPlan.created_at.desc())
        .first()
    )
    if existing:
        if include_segments:
            production_episode = db.query(ProductionEpisode).filter(
                ProductionEpisode.plan_id == existing.id,
                ProductionEpisode.episode_id == episode_id,
            ).one()
            ensure_shot_segments(db, production_episode.id)
        return existing
    return create_episode_production_plan(
        db,
        series_id,
        episode_id,
        target_duration_seconds=target_duration_seconds,
        budget_limit=budget_limit,
        include_segments=include_segments,
    )


def ensure_shot_segments(
    db: Session,
    production_episode_id: str,
    preferred_segment_seconds: float = MAX_SEGMENT_SECONDS,
) -> list[ProductionSegment]:
    production_episode = db.query(ProductionEpisode).filter(ProductionEpisode.id == production_episode_id).first()
    if not production_episode:
        raise ValueError("Production episode not found")

    existing = (
        db.query(ProductionSegment)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == production_episode_id)
        .order_by(ProductionSegment.order_index.asc(), ProductionSegment.id.asc())
        .all()
    )
    if existing:
        return existing

    shots = (
        db.query(ProductionShot)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == production_episode_id)
        .order_by(ProductionScene.order_index.asc(), ProductionShot.order_index.asc())
        .all()
    )
    created: list[ProductionSegment] = []
    for shot in shots:
        previous: ProductionSegment | None = None
        durations = _segment_durations(float(shot.duration_seconds or DEFAULT_FRAME_SECONDS), preferred_segment_seconds)
        for index, duration in enumerate(durations, start=1):
            segment = ProductionSegment(
                shot_plan_id=shot.id,
                previous_segment_id=previous.id if previous else None,
                segment_id=f"{shot.shot_id}-seg-{index:02d}",
                order_index=index,
                status=SEGMENT_PLANNED,
                duration_seconds=duration,
                continuity_mode=CONTINUITY_CONTINUOUS_ACTION if len(durations) > 1 else CONTINUITY_NARRATIVE_CUT,
                version=1,
                image_prompt=shot.action or "",
                video_prompt=shot.action or "",
                reference_roles_json=[],
            )
            db.add(segment)
            db.flush()
            created.append(segment)
            previous = segment
    db.commit()
    return created
