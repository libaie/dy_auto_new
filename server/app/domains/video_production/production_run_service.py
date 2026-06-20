import json

from sqlalchemy.orm import Session

from app.db.models.video_production import ProductionEpisode, ProductionPlan, ProductionScene, ProductionSegment, ProductionShot
from app.db_models import (
    Character,
    Episode,
    Scene,
    Series,
    VideoProductionRun,
)
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
from app.domains.ai_video_series.series_planning_service import (
    ensure_series_continuity_artifacts,
    generate_series_story_plan,
)
from app.domains.production_observability.production_observability_service import (
    record_production_event,
)
from app.domains.script_pipeline.script_pipeline_service import PipelineManager
from app.domains.script_pipeline.storyboard_timing import (
    annotate_storyboard_with_timing,
    build_detailed_image_prompt,
    build_detailed_video_prompt,
    format_time_range,
    shot_durations_for_total,
    timed_storyboard_lines,
)
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.video_production.production_plan_service import (
    create_episode_production_plan,
    ensure_shot_segments,
)
from app.domains.video_production.video_production_service import create_run_from_episode, start_image_stage
from app.domains.video_production.video_production_run_types import (
    LEGACY_EPISODE_RUN,
    MOCK_SERIES_SCALE,
    REAL_SHORT_E2E,
    validate_run_type,
)


REAL_SHORT_MIN_SECONDS = 5
REAL_SHORT_MAX_SECONDS = 28800
PREFERRED_SHOT_SECONDS = 8
SERIES_START_TEXT_ARTIFACTS = ("series_bible", "series_story_plan", "season_arc", "continuity_ledger")
EPISODE_START_TEXT_ARTIFACTS = (
    "episode_outline",
    "storyboard",
    "dialogue",
    "image_prompt",
    "video_prompt",
)


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


def _scale_frame_durations(frames: list[dict], target_duration_seconds: int | float) -> list[float]:
    target = round(float(target_duration_seconds), 2)
    current = [
        max(0.01, float(frame.get("duration") or frame.get("duration_seconds") or PREFERRED_SHOT_SECONDS))
        for frame in frames
    ]
    total = round(sum(current), 2)
    if total <= 0:
        values = [round(target / len(frames), 2) for _ in frames]
    else:
        values = [round(target * duration / total, 2) for duration in current]
    values[-1] = round(target - sum(values[:-1]), 2)
    return values


def _retime_storyboard_to_target(storyboard: dict, target_duration_seconds: int | None) -> dict:
    storyboard = annotate_storyboard_with_timing(storyboard, default_duration_seconds=PREFERRED_SHOT_SECONDS)
    if target_duration_seconds is None:
        return storyboard
    frames = storyboard.get("frames") if isinstance(storyboard.get("frames"), list) else []
    if not frames:
        return storyboard
    durations = _scale_frame_durations(frames, target_duration_seconds)
    retimed_frames = []
    for frame, duration in zip(frames, durations, strict=False):
        retimed = dict(frame)
        retimed["_previous_time_range"] = str(frame.get("time_range") or "")
        retimed["duration"] = duration
        retimed_frames.append(retimed)
    retimed_storyboard = annotate_storyboard_with_timing(
        {**storyboard, "frames": retimed_frames},
        default_duration_seconds=PREFERRED_SHOT_SECONDS,
    )
    for frame in retimed_storyboard.get("frames") or []:
        old_time_range = frame.pop("_previous_time_range", "")
        new_time_range = str(frame.get("time_range") or "")
        if old_time_range and new_time_range and old_time_range != new_time_range:
            for key in ("image_prompt", "video_prompt", "narration"):
                if isinstance(frame.get(key), str):
                    frame[key] = frame[key].replace(old_time_range, new_time_range)
    return retimed_storyboard


def _raise_if_latest_text_artifact_unapproved(
    service: AITextArtifactService,
    *,
    series_id: str,
    episode_id: str,
) -> None:
    affected_ids: list[str] = []
    for artifact_type in SERIES_START_TEXT_ARTIFACTS:
        artifact = service.latest_version(
            target_type="series",
            target_id=series_id,
            artifact_type=artifact_type,
        )
        if artifact and artifact.status != "approved":
            affected_ids.append(artifact.id)
    for artifact_type in EPISODE_START_TEXT_ARTIFACTS:
        artifact = service.latest_version(
            target_type="episode",
            target_id=episode_id,
            artifact_type=artifact_type,
        )
        if artifact and artifact.status != "approved":
            affected_ids.append(artifact.id)
    if affected_ids:
        raise ProductionRepairableError(
            code=ProductionErrorCode.TEXT_ARTIFACT_REVIEW_REQUIRED,
            message="Production has unapproved AI text artifact revisions.",
            cause="text_artifact_review_required",
            repair_action="Open AI text artifact workbench and approve or revise the latest text outputs before production.",
            repair_route=f"/series/{series_id}/ai-text-artifacts",
            retryable=True,
            affected_ids=affected_ids,
        )


def _storyboard_prompt_lines(storyboard: dict, key: str) -> list[str]:
    frames = storyboard.get("frames") or []
    if not isinstance(frames, list):
        return []
    return [str(frame.get(key) or "") for frame in frames if isinstance(frame, dict) and frame.get(key)]


def _storyboard_dialogue_lines(storyboard: dict) -> list[str]:
    frames = storyboard.get("frames") or []
    lines: list[str] = []
    if not isinstance(frames, list):
        return lines
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for key in ("dialogue", "narration", "voiceover"):
            value = frame.get(key)
            if isinstance(value, str) and value:
                lines.append(value)
            elif isinstance(value, list):
                lines.extend(str(item) for item in value if item)
    return lines


def _storyboard_content_text(storyboard: dict) -> str:
    timed_lines = timed_storyboard_lines(storyboard)
    return "\n".join(timed_lines or _storyboard_dialogue_lines(storyboard))


def _create_approved_import_artifact(
    service: AITextArtifactService,
    *,
    series_id: str,
    target_type: str,
    target_id: str,
    artifact_type: str,
    content_json: dict,
    content_text: str,
    episode_id: str | None = None,
) -> None:
    artifact = service.create_artifact(
        series_id=series_id,
        episode_id=episode_id,
        target_type=target_type,
        target_id=target_id,
        artifact_type=artifact_type,
        source_type="system_import",
        input_json={"source": "start_episode_production"},
        content_json=content_json,
        content_text=content_text,
        model_trace_json={"source": "start_episode_production", "stage": "text_artifact_import"},
        created_by="system",
    )
    service.approve_artifact(artifact.id, actor_user_id="system")


def _ensure_episode_start_text_artifacts(
    db: Session,
    service: AITextArtifactService,
    *,
    series: Series,
    episode: Episode,
    storyboard: dict,
) -> None:
    ensure_series_continuity_artifacts(db, series.id)
    if not service.latest_approved(
        target_type="series",
        target_id=series.id,
        artifact_type="series_bible",
    ):
        _create_approved_import_artifact(
            service,
            series_id=series.id,
            target_type="series",
            target_id=series.id,
            artifact_type="series_bible",
            content_json=series.story_bible_json if isinstance(series.story_bible_json, dict) else {},
            content_text=series.logline or series.title,
        )
    if not service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="storyboard",
    ):
        _create_approved_import_artifact(
            service,
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="storyboard",
            content_json=storyboard,
            content_text=_storyboard_content_text(storyboard),
        )
    if isinstance(episode.script_json, dict) and episode.script_json and not service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
    ):
        _create_approved_import_artifact(
            service,
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_script",
            content_json=episode.script_json,
            content_text=json.dumps(episode.script_json, ensure_ascii=False),
        )
    dialogue_lines = _storyboard_dialogue_lines(storyboard)
    if not service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="dialogue",
    ):
        _create_approved_import_artifact(
            service,
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="dialogue",
            content_json={"lines": dialogue_lines},
            content_text="\n".join(dialogue_lines),
        )
    image_prompts = _storyboard_prompt_lines(storyboard, "image_prompt")
    if not service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="image_prompt",
    ):
        _create_approved_import_artifact(
            service,
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="image_prompt",
            content_json={"prompts": image_prompts},
            content_text="\n".join(image_prompts),
        )
    video_prompts = _storyboard_prompt_lines(storyboard, "video_prompt")
    if not service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="video_prompt",
    ):
        _create_approved_import_artifact(
            service,
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="video_prompt",
            content_json={"prompts": video_prompts},
            content_text="\n".join(video_prompts),
        )


def _real_short_storyboard_needs_reference_rebuild(storyboard: dict) -> bool:
    frames = storyboard.get("frames") or []
    if not frames:
        return True
    for frame in frames:
        if not isinstance(frame, dict):
            return True
        if not frame.get("reference_urls") or not frame.get("scene_id") or not frame.get("character_ids"):
            return True
    return False


def _dedupe_refs(refs: list[str], limit: int | None = None) -> list[str]:
    deduped = list(dict.fromkeys([ref for ref in refs if ref]))
    return deduped[:limit] if limit else deduped


def _style_item_refs(items: list[dict], item_id: str | None) -> list[str]:
    for item in items:
        if item.get("id") == item_id:
            return item.get("reference_urls") or []
    return []


def _style_locked_reference_payload(series: Series, frame_index: int, frame: dict) -> dict:
    style_lock = _style_lock(series)
    characters = style_lock.get("characters") if isinstance(style_lock.get("characters"), list) else []
    scenes = style_lock.get("scenes") if isinstance(style_lock.get("scenes"), list) else []
    visual_style = style_lock.get("visual_style") if isinstance(style_lock.get("visual_style"), dict) else {}
    style_refs = _dedupe_refs(visual_style.get("reference_urls") or [], 3)
    character_ids = frame.get("character_ids") or [item.get("id") for item in characters if item.get("id")][:1]
    scene = scenes[frame_index % len(scenes)] if scenes else {}
    scene_id = frame.get("scene_id") or scene.get("id")
    character_reference_urls = []
    for character_id in character_ids:
        character_reference_urls.extend(_style_item_refs(characters, character_id))
    style_reference_urls = _dedupe_refs((scene.get("reference_urls") or []) + style_refs, 3)
    reference_urls = _dedupe_refs((frame.get("reference_urls") or []) + character_reference_urls[:9] + style_reference_urls)
    return {
        "character_ids": character_ids,
        "scene_id": scene_id,
        "reference_urls": reference_urls,
        "character_reference_urls": _dedupe_refs(character_reference_urls, 9),
        "style_reference_urls": style_reference_urls,
        "reference_instructions": (
            "Use @Image 1 to lock character face, hairstyle, outfit, and body proportions. "
            "Use the scene/style references to lock lighting, palette, and environment continuity."
        ) if reference_urls else "",
        "visual_style_prompt": visual_style.get("prompt") or "",
        "scene_name": scene.get("name") or "",
    }


def _enrich_storyboard_with_style_refs(storyboard: dict, series: Series) -> dict:
    timed_storyboard = annotate_storyboard_with_timing(
        storyboard,
        default_duration_seconds=PREFERRED_SHOT_SECONDS,
    )
    frames = []
    for index, frame in enumerate(timed_storyboard.get("frames") or []):
        enriched = dict(frame)
        payload = _style_locked_reference_payload(series, index, enriched)
        for key in (
            "character_ids",
            "scene_id",
            "reference_urls",
            "character_reference_urls",
            "style_reference_urls",
            "reference_instructions",
        ):
            if payload.get(key):
                enriched[key] = payload[key]
        frames.append(enriched)
    timed_storyboard["frames"] = frames
    return timed_storyboard


def _compact_artifact_content(value, *, max_chars: int = 1400) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= max_chars else f"{text[:max_chars]}..."


def _approved_story_context(service: AITextArtifactService, series: Series, episode: Episode) -> str:
    specs = [
        ("series", series.id, "series_story_plan", "整季故事规划"),
        ("series", series.id, "season_arc", "季弧线"),
        ("series", series.id, "continuity_ledger", "连续性台账"),
        ("episode", episode.id, "episode_outline", "本集故事卡"),
    ]
    lines: list[str] = []
    for target_type, target_id, artifact_type, label in specs:
        artifact = service.latest_approved(
            target_type=target_type,
            target_id=target_id,
            artifact_type=artifact_type,
        )
        if not artifact:
            continue
        content = artifact.content_json if artifact.content_json else artifact.content_text
        compact = _compact_artifact_content(content)
        if compact:
            lines.append(f"{label} v{artifact.version}: {compact}")
    return "\n".join(lines)


def _style_lock_name_maps(series: Series) -> tuple[dict[str, str], dict[str, str]]:
    style_lock = _style_lock(series)
    character_names: dict[str, str] = {}
    scene_names: dict[str, str] = {}
    for item in style_lock.get("characters") or []:
        if isinstance(item, dict) and item.get("id"):
            character_names[str(item["id"])] = str(item.get("name") or item["id"])
    for item in style_lock.get("scenes") or []:
        if isinstance(item, dict) and item.get("id"):
            scene_names[str(item["id"])] = str(item.get("name") or item["id"])
    for character in series.characters or []:
        character_names.setdefault(character.id, character.name)
    for scene in series.scenes or []:
        scene_names.setdefault(scene.id, scene.name)
    return character_names, scene_names


def _series_asset_pool_summary(series: Series) -> dict:
    character_names, scene_names = _style_lock_name_maps(series)
    return {
        "characters": [{"id": asset_id, "name": name} for asset_id, name in character_names.items()],
        "scenes": [{"id": asset_id, "name": name} for asset_id, name in scene_names.items()],
    }


def _usage_items(asset_usage: dict, key: str, ids: list[str], names: dict[str, str]) -> list[dict]:
    raw_items = asset_usage.get(key) if isinstance(asset_usage.get(key), list) else []
    by_id = {
        str(item.get("id")): item
        for item in raw_items
        if isinstance(item, dict) and item.get("id")
    }
    items = []
    for asset_id in ids:
        item = dict(by_id.get(asset_id) or {})
        item["id"] = asset_id
        item.setdefault("name", names.get(asset_id, asset_id))
        item.setdefault("source", "existing")
        if not item.get("usage"):
            item["usage"] = "本集剧情资产。"
        items.append(item)
    return items


def _episode_asset_scope_from_outline(service: AITextArtifactService, series: Series, episode: Episode) -> dict:
    artifact = service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
    )
    content = artifact.content_json if artifact and isinstance(artifact.content_json, dict) else {}
    character_ids = list(dict.fromkeys(str(item) for item in (content.get("character_ids") or []) if item))
    scene_ids = list(dict.fromkeys(str(item) for item in (content.get("scene_ids") or []) if item))
    character_names, scene_names = _style_lock_name_maps(series)
    asset_usage = content.get("asset_usage") if isinstance(content.get("asset_usage"), dict) else {}
    return {
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "source": "episode_outline" if artifact else "missing_episode_outline",
        "characters": _usage_items(asset_usage, "characters", character_ids, character_names),
        "scenes": _usage_items(asset_usage, "scenes", scene_ids, scene_names),
        "asset_usage": asset_usage,
        "generated_assets": content.get("generated_assets") if isinstance(content.get("generated_assets"), dict) else {"characters": [], "scenes": []},
    }


def _script_episode_asset_scope(episode: Episode) -> dict:
    script = episode.script_json if isinstance(episode.script_json, dict) else {}
    scope = script.get("episode_asset_scope") if isinstance(script.get("episode_asset_scope"), dict) else {}
    character_ids = list(dict.fromkeys(str(item) for item in (scope.get("character_ids") or []) if item))
    scene_ids = list(dict.fromkeys(str(item) for item in (scope.get("scene_ids") or []) if item))
    if not character_ids or not scene_ids:
        return {}
    return {
        **scope,
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "source": scope.get("source") or "episode_script",
    }


def _episode_asset_scope_for_production(
    service: AITextArtifactService,
    series: Series,
    episode: Episode,
) -> dict:
    script_scope = _script_episode_asset_scope(episode)
    if script_scope:
        return script_scope
    return _episode_asset_scope_from_outline(service, series, episode)


def _scope_has_assets(scope: dict) -> bool:
    return bool(scope.get("character_ids")) and bool(scope.get("scene_ids"))


def _scope_needs_scene_mapping(scope: dict) -> bool:
    scene_ids = [str(item) for item in scope.get("scene_ids") or [] if item]
    scene_map = scope.get("scene_by_scene_number") if isinstance(scope.get("scene_by_scene_number"), dict) else {}
    return len(scene_ids) > 1 and not scene_map


def _style_lock_ids(series: Series, key: str) -> set[str]:
    rows = _style_lock(series).get(key) or []
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }


def _series_asset_ids(series: Series, relation_name: str, style_lock_key: str) -> set[str]:
    related = getattr(series, relation_name, []) or []
    return {
        str(item.id)
        for item in related
        if getattr(item, "id", None)
    } | _style_lock_ids(series, style_lock_key)


def _raise_episode_asset_scope_missing(
    series: Series,
    episode: Episode,
    *,
    message: str = "本集缺少角色或场景作用域，无法进入视频生产。",
    cause: str | None = None,
    affected_ids: list[str] | None = None,
) -> None:
    raise ProductionRepairableError(
        code=ProductionErrorCode.EPISODE_ASSET_SCOPE_MISSING,
        message=message,
        cause=cause,
        repair_action="先生成或修复本集故事规划和剧本分镜，让每个分镜带有 scene_id 与 character_ids。",
        repair_route=f"/series/{series.id}",
        retryable=False,
        affected_ids=affected_ids or [episode.id],
    )


def _validate_episode_asset_scope_ids(db: Session, series: Series, episode: Episode, scope: dict) -> None:
    if not _scope_has_assets(scope):
        return
    character_ids = [str(item) for item in scope.get("character_ids") or [] if item]
    scene_ids = [str(item) for item in scope.get("scene_ids") or [] if item]
    style_lock_character_ids = _style_lock_ids(series, "characters")
    style_lock_scene_ids = _style_lock_ids(series, "scenes")
    allowed_character_ids = _series_asset_ids(series, "characters", "characters")
    allowed_scene_ids = _series_asset_ids(series, "scenes", "scenes")
    existing_character_ids = {
        row.id
        for row in db.query(Character.id).filter(Character.id.in_(character_ids)).all()
    }
    existing_scene_ids = {
        row.id
        for row in db.query(Scene.id).filter(Scene.id.in_(scene_ids)).all()
    }
    invalid_character_ids = [
        asset_id
        for asset_id in character_ids
        if asset_id not in allowed_character_ids
        or (asset_id not in existing_character_ids and asset_id not in style_lock_character_ids)
    ]
    invalid_scene_ids = [
        asset_id
        for asset_id in scene_ids
        if asset_id not in allowed_scene_ids
        or (asset_id not in existing_scene_ids and asset_id not in style_lock_scene_ids)
    ]
    if invalid_character_ids or invalid_scene_ids:
        _raise_episode_asset_scope_missing(
            series,
            episode,
            message="本集角色或场景作用域引用了不存在或未关联到系列的资产。",
            cause="invalid_episode_asset_scope",
            affected_ids=[episode.id, *invalid_character_ids, *invalid_scene_ids],
        )


def _apply_episode_asset_scope_to_storyboard(storyboard: dict, scope: dict) -> dict:
    if not _scope_has_assets(scope):
        return storyboard
    frames = storyboard.get("frames") if isinstance(storyboard.get("frames"), list) else []
    if not frames:
        return storyboard
    scene_ids = [str(item) for item in scope.get("scene_ids") or [] if item]
    character_ids = list(dict.fromkeys(str(item) for item in scope.get("character_ids") or [] if item))
    scene_map = scope.get("scene_by_scene_number") if isinstance(scope.get("scene_by_scene_number"), dict) else {}
    enriched_frames = []
    for frame in frames:
        if not isinstance(frame, dict):
            enriched_frames.append(frame)
            continue
        enriched = dict(frame)
        scene_number = enriched.get("scene_number")
        mapped_scene_id = scene_map.get(str(scene_number)) or scene_map.get(scene_number)
        if mapped_scene_id and str(mapped_scene_id) in scene_ids:
            enriched["scene_id"] = str(mapped_scene_id)
        elif len(scene_ids) == 1:
            enriched["scene_id"] = scene_ids[0]
        elif enriched.get("scene_id") and str(enriched["scene_id"]) not in scene_ids:
            enriched.pop("scene_id", None)
        if not enriched.get("character_ids"):
            enriched["character_ids"] = character_ids
        else:
            scoped_frame_character_ids = [
                str(item)
                for item in enriched.get("character_ids") or []
                if str(item) in character_ids
            ]
            enriched["character_ids"] = scoped_frame_character_ids or character_ids
        enriched_frames.append(enriched)
    return {**storyboard, "frames": enriched_frames}


def _storyboard_has_frame_asset_scope(storyboard: dict) -> bool:
    frames = storyboard.get("frames") if isinstance(storyboard.get("frames"), list) else []
    return bool(frames) and all(
        isinstance(frame, dict) and frame.get("scene_id") and frame.get("character_ids")
        for frame in frames
    )


def _ensure_episode_asset_scope_ready(series: Series, episode: Episode, storyboard: dict, scope: dict) -> None:
    if _scope_has_assets(scope) and _storyboard_has_frame_asset_scope(storyboard):
        return
    _raise_episode_asset_scope_missing(series, episode)


def _episode_script_missing(service: AITextArtifactService, episode: Episode) -> bool:
    if isinstance(episode.script_json, dict) and episode.script_json:
        return False
    return service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
    ) is None


def _script_generation_source_prompt(
    service: AITextArtifactService,
    series: Series,
    episode: Episode,
    *,
    episode_asset_scope: dict | None = None,
) -> str:
    episode_scope = episode_asset_scope or _episode_asset_scope_from_outline(service, series, episode)
    parts = [
        f"系列标题: {series.title or ''}",
        f"系列梗概: {series.logline or ''}",
        f"类型: {series.genre or ''}",
        f"第{episode.episode_number}集标题: {episode.title or ''}",
        "请生成可直接用于短视频生产的分集故事脚本和分镜。",
        "每个分镜必须写清楚该秒段的具体剧情、画面动作、镜头运动和旁白。",
    ]
    if episode_scope.get("character_ids") or episode_scope.get("scene_ids"):
        parts.extend([
            "本集资产清单：",
            json.dumps(episode_scope, ensure_ascii=False, sort_keys=True),
            "系列资产池仅用于连续性参考，不得替代本集资产清单：",
            json.dumps(_series_asset_pool_summary(series), ensure_ascii=False, sort_keys=True),
        ])
    story_context = _approved_story_context(service, series, episode)
    if story_context:
        parts.extend([
            "已批准的系列故事上下文如下，必须承接这些设定和集间钩子：",
            story_context,
        ])
    return "\n".join(part for part in parts if part and not part.endswith(": "))


def _series_script_tags(series: Series) -> list[str]:
    tags = []
    if series.genre:
        tags.append(str(series.genre))
    story_bible = series.story_bible_json if isinstance(series.story_bible_json, dict) else {}
    for value in story_bible.get("tags") or []:
        if isinstance(value, str) and value:
            tags.append(value)
    return list(dict.fromkeys(tags))


async def _try_generate_script_storyboard(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    artifact_service: AITextArtifactService,
    target_duration_seconds: int,
) -> tuple[dict | None, dict | None]:
    episode_asset_scope = _episode_asset_scope_from_outline(artifact_service, series, episode)
    try:
        await PipelineManager().start_or_resume(
            db,
            series_id=series.id,
            episode_id=episode.id,
            source_prompt=_script_generation_source_prompt(
                artifact_service,
                series,
                episode,
                episode_asset_scope=episode_asset_scope,
            ),
            tags=_series_script_tags(series),
            target_duration_seconds=target_duration_seconds,
            episode_asset_scope=episode_asset_scope,
        )
    except Exception as exc:
        return None, {
            "stage": "script_generation",
            "stage_status": "fallback",
            "error_code": exc.__class__.__name__,
            "error_message": str(exc),
        }
    db.refresh(episode)
    storyboard = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {}
    if storyboard.get("frames"):
        return _enrich_storyboard_with_style_refs(storyboard, series), None
    return None, {
        "stage": "script_generation",
        "stage_status": "fallback",
        "error_code": "SCRIPT_STORYBOARD_EMPTY",
        "error_message": "script generation completed without storyboard frames",
    }


async def generate_episode_script_storyboard(
    db: Session,
    *,
    series_id: str,
    episode_id: str,
    target_duration_seconds: int | None = None,
) -> dict:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise ValueError("episode_not_found")

    await generate_series_story_plan(db, series_id)
    db.refresh(series)
    db.refresh(episode)
    artifact_service = AITextArtifactService(db)
    effective_target = int(target_duration_seconds or series.target_duration or episode.duration_seconds or 60)
    episode_asset_scope = _episode_asset_scope_from_outline(artifact_service, series, episode)
    script = await PipelineManager().start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt=_script_generation_source_prompt(
            artifact_service,
            series,
            episode,
            episode_asset_scope=episode_asset_scope,
        ),
        tags=_series_script_tags(series),
        target_duration_seconds=effective_target,
        episode_asset_scope=episode_asset_scope,
    )
    db.refresh(episode)
    script_json = episode.script_json if isinstance(episode.script_json, dict) else script.model_dump(mode="json")
    storyboard_json = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {}
    return {
        "series_id": series.id,
        "episode_id": episode.id,
        "script": script_json,
        "storyboard": storyboard_json,
    }


def _fallback_story_beat(
    *,
    index: int,
    frame_count: int,
    time_range: str,
    series: Series,
    episode: Episode,
    character_name: str,
    scene_name: str,
) -> dict[str, str]:
    premise = series.logline or series.title or "本集主线"
    episode_name = episode.title or f"第{episode.episode_number}集"
    templates = [
        {
            "narration": f"{time_range}，{episode_name}开场：{character_name}在{scene_name}撞见关键异常。",
            "action": "用强视觉钩子抛出本集冲突",
            "emotion": "震惊",
            "shot_type": "wide",
        },
        {
            "narration": f"{time_range}，矛盾升级：{character_name}被迫面对选择，主线压力变得具体。",
            "action": "把冲突对象、危险或目标摆到画面中心",
            "emotion": "紧张",
            "shot_type": "medium",
        },
        {
            "narration": f"{time_range}，线索出现：{premise}里的关键信息被看见。",
            "action": "展示能够推动下一步行动的证据或反应",
            "emotion": "警觉",
            "shot_type": "close_up",
        },
        {
            "narration": f"{time_range}，人物行动：{character_name}做出反击或追问，关系开始反转。",
            "action": "让角色完成明确动作，不停留在气氛描述",
            "emotion": "痛快",
            "shot_type": "medium",
        },
        {
            "narration": f"{time_range}，结尾钩子：新的问题出现，推动下一段继续观看。",
            "action": "留下悬念、反应或未完成动作",
            "emotion": "悬念",
            "shot_type": "close_up",
        },
    ]
    if index == frame_count - 1:
        return templates[-1]
    return templates[index % (len(templates) - 1)]


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
    durations = shot_durations_for_total(duration, preferred_seconds=PREFERRED_SHOT_SECONDS)
    frame_count = len(durations)
    character_ids = [item.get("id") for item in characters if item.get("id")]
    default_character_ids = character_ids[:1]
    frames = []
    elapsed = 0.0
    for index, frame_duration in enumerate(durations):
        scene = scenes[index % len(scenes)] if scenes else {}
        scene_id = scene.get("id")
        character_name = (characters[0] or {}).get("name") if characters else "主角"
        scene_name = scene.get("name") or "锁定场景"
        time_range = format_time_range(elapsed, elapsed + frame_duration)
        story_beat = _fallback_story_beat(
            index=index,
            frame_count=frame_count,
            time_range=time_range,
            series=series,
            episode=episode,
            character_name=character_name,
            scene_name=scene_name,
        )
        character_reference_urls = []
        for character_id in default_character_ids:
            character_reference_urls.extend(_style_item_refs(characters, character_id))
        style_reference_urls = _dedupe_refs((scene.get("reference_urls") or []) + style_refs, 3)
        reference_urls = _dedupe_refs(character_reference_urls[:9] + style_reference_urls)
        frame_id = f"frame-{index + 1:03d}"
        frames.append({
            "index": index,
            "frame_id": frame_id,
            "narration": story_beat["narration"],
            "image_prompt": build_detailed_image_prompt(
                time_range=time_range,
                subject=character_name,
                scene=scene_name,
                action=story_beat["action"],
                shot_type=story_beat["shot_type"],
                emotion=story_beat["emotion"],
                visual_style=visual_style.get("prompt") or "",
                raw_prompt=f"{series.logline or series.title or 'Generate the next coherent shot.'} {story_beat['action']}.",
                continuity="Keep character identity, outfit, lighting, color palette, and lens language consistent with the locked references.",
            ),
            "video_prompt": build_detailed_video_prompt(
                time_range=time_range,
                subject=character_name,
                scene=scene_name,
                action=story_beat["action"],
                shot_type=story_beat["shot_type"],
                camera_movement="static",
                emotion=story_beat["emotion"],
                raw_prompt=story_beat["action"],
                continuity="Keep posture, eyeline, props, lighting, and action continuity from the previous timed beat.",
            ),
            "duration": frame_duration,
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
            "shot_type": story_beat["shot_type"],
            "camera_movement": "static",
            "action": story_beat["action"],
            "emotion": story_beat["emotion"],
        })
        elapsed = round(elapsed + frame_duration, 2)
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
    storyboard = annotate_storyboard_with_timing(storyboard, default_duration_seconds=PREFERRED_SHOT_SECONDS)
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
    prepare_text_artifacts: bool = False,
    episode_asset_scope_override: dict | None = None,
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
    artifact_service = AITextArtifactService(db)
    _raise_if_latest_text_artifact_unapproved(
        artifact_service,
        series_id=series_id,
        episode_id=episode_id,
    )
    if prepare_text_artifacts:
        await generate_series_story_plan(db, series_id)
        db.refresh(series)
        db.refresh(episode)
    approved_storyboard = artifact_service.latest_approved(
        target_type="episode",
        target_id=episode_id,
        artifact_type="storyboard",
    )
    if approved_storyboard and isinstance(approved_storyboard.content_json, dict):
        approved_storyboard_json = dict(approved_storyboard.content_json)
        if isinstance(approved_storyboard_json.get("frames"), list) and approved_storyboard_json["frames"]:
            episode.storyboard_json = _enrich_storyboard_with_style_refs(approved_storyboard_json, series)
            db.flush()

    storyboard = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {}
    effective_target = int(target_duration_seconds or series.target_duration or episode.duration_seconds or 60)
    generation_error = None
    script_generation_attempted = False
    if prepare_text_artifacts and _episode_script_missing(artifact_service, episode):
        script_generation_attempted = True
        generated_storyboard, generation_error = await _try_generate_script_storyboard(
            db,
            series=series,
            episode=episode,
            artifact_service=artifact_service,
            target_duration_seconds=effective_target,
        )
        if generated_storyboard:
            storyboard = generated_storyboard
            episode.storyboard_json = storyboard
            db.flush()
    if storyboard.get("frames"):
        storyboard = _enrich_storyboard_with_style_refs(storyboard, series)
        episode.storyboard_json = storyboard
        db.flush()
    if (
        not storyboard.get("frames")
        or (run_type == REAL_SHORT_E2E and _real_short_storyboard_needs_reference_rebuild(storyboard))
    ):
        generated_storyboard = None
        if not storyboard.get("frames") and not script_generation_attempted:
            generated_storyboard, generation_error = await _try_generate_script_storyboard(
                db,
                series=series,
                episode=episode,
                artifact_service=artifact_service,
                target_duration_seconds=effective_target,
            )
        if generated_storyboard:
            storyboard = generated_storyboard
            episode.storyboard_json = storyboard
            db.flush()
        if (
            not storyboard.get("frames")
            or (run_type == REAL_SHORT_E2E and _real_short_storyboard_needs_reference_rebuild(storyboard))
        ):
            if episode_asset_scope_override is not None:
                fallback_scope = episode_asset_scope_override
            elif prepare_text_artifacts:
                fallback_scope = _episode_asset_scope_for_production(artifact_service, series, episode)
            else:
                fallback_scope = {}
            if prepare_text_artifacts or episode_asset_scope_override is not None:
                _validate_episode_asset_scope_ids(db, series, episode, fallback_scope)
                if not _scope_has_assets(fallback_scope):
                    _raise_episode_asset_scope_missing(series, episode)
                if _scope_needs_scene_mapping(fallback_scope):
                    _raise_episode_asset_scope_missing(
                        series,
                        episode,
                        message="本集包含多个场景，但缺少 scene_by_scene_number 映射，无法安全生成兜底分镜。",
                        cause="ambiguous_episode_scene_scope",
                    )
            storyboard = _build_style_locked_storyboard(
                db,
                series=series,
                episode=episode,
                target_duration_seconds=effective_target,
            )
            if generation_error:
                storyboard["generation_trace"] = generation_error
                episode.storyboard_json = storyboard
                db.flush()
    effective_duration = target_duration_seconds or series.target_duration or episode.duration_seconds or _target_duration_from_storyboard(storyboard)
    _assert_real_short_duration(run_type, effective_duration)
    if episode_asset_scope_override is not None:
        episode_asset_scope = episode_asset_scope_override
    elif prepare_text_artifacts:
        episode_asset_scope = _episode_asset_scope_for_production(artifact_service, series, episode)
    else:
        episode_asset_scope = _script_episode_asset_scope(episode)
    if episode_asset_scope:
        _validate_episode_asset_scope_ids(db, series, episode, episode_asset_scope)
        storyboard = _apply_episode_asset_scope_to_storyboard(storyboard, episode_asset_scope)
    storyboard = _retime_storyboard_to_target(storyboard, target_duration_seconds)
    episode.storyboard_json = storyboard
    db.flush()
    if prepare_text_artifacts or episode_asset_scope_override is not None:
        _ensure_episode_asset_scope_ready(series, episode, storyboard, episode_asset_scope)
    if prepare_text_artifacts:
        _ensure_episode_start_text_artifacts(
            db,
            artifact_service,
            series=series,
            episode=episode,
            storyboard=storyboard,
        )

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
    artifact_service.bind_latest_approved_for_episode_run(
        series_id=series_id,
        episode_id=episode_id,
        run_id=run.id,
        production_plan_id=run.production_plan_id,
    )
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
