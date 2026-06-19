from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db_models import Episode, Series
from app.services.ai_text_artifact_service import AITextArtifactService
from app.domains.ai_video_series.episode_asset_scope_service import normalize_episode_asset_scope
from app.domains.ai_video_series.story_generator_expert import generate_story_plan_with_expert


FINISHED_EPISODE_STATUSES = {"done", "completed"}
REPLACEABLE_SOURCE_TYPES = {"system_backfill", "legacy_run_backfill"}


@dataclass(frozen=True)
class EpisodePlaceholderResult:
    series_id: str
    target_episode_count: int
    existing_episode_numbers: list[int]
    created_episode_numbers: list[int]


@dataclass(frozen=True)
class ContinuityArtifactResult:
    series_id: str
    created_continuity_ledger: bool
    created_outline_episode_numbers: list[int]


@dataclass(frozen=True)
class SeriesStoryPlanResult:
    series_id: str
    target_episode_count: int
    created_episode_numbers: list[int]
    replaced_outline_episode_numbers: list[int]
    preserved_outline_episode_numbers: list[int]
    artifacts: list[dict[str, Any]]
    model_trace: dict[str, Any]


def _target_episode_count(series: Series) -> int:
    return max(1, int(series.total_episodes or 1))


def _style_lock(series: Series) -> dict[str, Any]:
    story_bible = series.story_bible_json if isinstance(series.story_bible_json, dict) else {}
    style_lock = story_bible.get("style_lock") or {}
    return style_lock if isinstance(style_lock, dict) else {}


def _ids_from_style_lock(series: Series, key: str, relation_name: str) -> list[str]:
    style_lock = _style_lock(series)
    rows = style_lock.get(key) or []
    ids = []
    if isinstance(rows, list):
        ids = [str(row["id"]) for row in rows if isinstance(row, dict) and row.get("id")]
    if ids:
        return list(dict.fromkeys(ids))
    related = getattr(series, relation_name, []) or []
    return list(dict.fromkeys(str(item.id) for item in related if getattr(item, "id", None)))


def _episode_outline(
    series: Series,
    episode: Episode,
    *,
    total_episodes: int,
    character_ids: list[str],
    scene_ids: list[str],
) -> dict[str, Any]:
    episode_number = int(episode.episode_number)
    mainline = series.logline or series.title
    previous_handoff = "" if episode_number == 1 else f"承接第 {episode_number - 1} 集的人物状态、未解线索和情绪余波。"
    next_handoff = "完成系列主线收束。" if episode_number >= total_episodes else f"留下通往第 {episode_number + 1} 集的新线索。"
    return {
        "schema_version": "series.episode_outline.v1",
        "episode_number": episode_number,
        "title": episode.title or f"Episode {episode_number}",
        "hook": (
            f"用一个直接牵动主线的问题开场：{mainline}"
            if episode_number == 1
            else f"从第 {episode_number - 1} 集留下的情绪和线索切入。"
        ),
        "episode_goal": (
            f"建立主线悬念：{mainline}"
            if episode_number == 1
            else f"推进主线第 {episode_number} 阶段，并保持人物动机与前序一致。"
        ),
        "previous_episode_handoff": previous_handoff,
        "central_conflict": mainline,
        "reversal": f"第 {episode_number} 集中段让角色对主线真相产生新的误判或代价。",
        "cliffhanger": next_handoff,
        "next_episode_handoff": next_handoff,
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "character_state_changes": [
            {
                "character_id": character_id,
                "change": "introduced" if episode_number == 1 else "continues from prior episode state",
            }
            for character_id in character_ids
        ],
        "foreshadowing_introduced": [] if episode_number >= total_episodes else [next_handoff],
        "foreshadowing_resolved": [] if episode_number == 1 else [previous_handoff],
        "next_hook": next_handoff,
    }


def _continuity_ledger(
    series: Series,
    episodes: list[Episode],
    *,
    character_ids: list[str],
    scene_ids: list[str],
) -> dict[str, Any]:
    total_episodes = _target_episode_count(series)
    return {
        "schema_version": "series.continuity_ledger.v1",
        "series_id": series.id,
        "total_episodes": total_episodes,
        "mainline": series.logline or series.title,
        "episode_timeline": [
            {
                "episode_number": int(episode.episode_number),
                "title": episode.title or f"Episode {episode.episode_number}",
                "handoff_to_next": (
                    "series_finale"
                    if int(episode.episode_number) >= total_episodes
                    else f"handoff_to_episode_{int(episode.episode_number) + 1}"
                ),
            }
            for episode in episodes
        ],
        "character_states": [
            {"character_id": character_id, "state": "must remain visually and behaviorally consistent across episodes"}
            for character_id in character_ids
        ],
        "scene_anchors": [
            {"scene_id": scene_id, "state": "must keep location identity consistent across episodes"}
            for scene_id in scene_ids
        ],
        "open_foreshadowing": [
            {
                "introduced_episode": int(episode.episode_number),
                "promise": f"第 {episode.episode_number} 集结尾必须自然承接下一集。",
            }
            for episode in episodes
            if int(episode.episode_number) < total_episodes
        ],
        "forbidden_contradictions": [
            "Do not change established character identity, motivation, or visual anchors without an explicit approved revision.",
            "Do not resolve a prior episode hook off-screen without recording it in the next episode outline.",
        ],
    }


def _series_story_plan(
    series: Series,
    episodes: list[Episode],
    *,
    character_ids: list[str],
    scene_ids: list[str],
) -> dict[str, Any]:
    mainline = series.logline or series.title
    return {
        "schema_version": "series.story_plan.v1",
        "series_id": series.id,
        "title": series.title,
        "logline": mainline,
        "target_episode_count": _target_episode_count(series),
        "story_engine": mainline,
        "season_promise": f"每一集都围绕“{mainline}”推进一个更具体的情绪和线索问题。",
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "episode_numbers": [int(episode.episode_number) for episode in episodes],
    }


def _season_arc(series: Series, episodes: list[Episode]) -> dict[str, Any]:
    total = _target_episode_count(series)
    mainline = series.logline or series.title
    return {
        "schema_version": "series.season_arc.v1",
        "series_id": series.id,
        "arc_summary": f"从主线设问开始，逐集升级冲突，并在第 {total} 集完成情绪与线索收束：{mainline}",
        "turning_points": [
            {
                "episode_number": int(episode.episode_number),
                "beat": (
                    "setup"
                    if int(episode.episode_number) == 1
                    else "finale"
                    if int(episode.episode_number) >= total
                    else "escalation"
                ),
                "purpose": episode.title or f"Episode {episode.episode_number}",
            }
            for episode in episodes
        ],
    }


def _planning_system_prompt() -> str:
    return (
        "你是短剧整季故事规划助手。必须只输出可解析 JSON，不要 Markdown。"
        "JSON 必须包含 series_story_plan、season_arc、episode_outlines。"
        "每个 episode_outline 必须包含 episode_number、title、hook、episode_goal、central_conflict、"
        "reversal、cliffhanger、previous_episode_handoff、next_episode_handoff、"
        "character_state_changes、foreshadowing_introduced、foreshadowing_resolved、character_ids、scene_ids。"
    )


def _planning_user_prompt(
    series: Series,
    episodes: list[Episode],
    *,
    character_ids: list[str],
    scene_ids: list[str],
    existing_artifacts: list[dict[str, Any]],
) -> str:
    context = {
        "series": {
            "id": series.id,
            "title": series.title,
            "logline": series.logline,
            "total_episodes": _target_episode_count(series),
            "story_bible_json": series.story_bible_json if isinstance(series.story_bible_json, dict) else {},
        },
        "episodes": [
            {
                "id": episode.id,
                "episode_number": int(episode.episode_number),
                "title": episode.title or f"Episode {episode.episode_number}",
            }
            for episode in episodes
        ],
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "existing_approved_artifacts": existing_artifacts,
    }
    return "\n".join([
        "请根据以下上下文生成整季故事规划。不要生成分镜或逐秒脚本。",
        "输出 JSON 结构：",
        '{"series_story_plan": {...}, "season_arc": {...}, "episode_outlines": [{...}]}',
        json.dumps(context, ensure_ascii=False, indent=2),
    ])


def _existing_artifact_context(
    service: AITextArtifactService,
    series: Series,
    episodes: list[Episode],
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for artifact_type in ("series_bible", "series_story_plan", "season_arc", "continuity_ledger"):
        artifact = service.latest_approved(
            target_type="series",
            target_id=series.id,
            artifact_type=artifact_type,
        )
        if artifact:
            artifacts.append(_artifact_summary(artifact))
    for episode in episodes:
        artifact = service.latest_approved(
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
        )
        if artifact:
            summary = _artifact_summary(artifact)
            summary["episode_number"] = int(episode.episode_number)
            artifacts.append(summary)
    return artifacts


def _parse_planning_json(raw_text: str) -> dict[str, Any]:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("AI output was empty")
    text = raw_text.strip()
    candidates = [text]
    if "```" in text:
        for part in text.split("```"):
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate:
                candidates.append(candidate)

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            return parsed

        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate[index:])
            except JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise ValueError("AI output was not valid planning JSON")


def _episode_outline_sources(parsed: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = (
        parsed.get("episode_outlines")
        or parsed.get("episodes")
        or parsed.get("episode_cards")
        or []
    )
    if isinstance(rows, dict):
        rows = list(rows.values())
    if not isinstance(rows, list):
        return {}

    by_number: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_number = row.get("episode_number") or row.get("number")
        try:
            episode_number = int(raw_number)
        except (TypeError, ValueError):
            continue
        by_number[episode_number] = row
    return by_number


def _merge_series_payload(fallback: dict[str, Any], parsed: dict[str, Any], *keys: str) -> dict[str, Any]:
    merged = dict(fallback)
    for key in keys:
        value = parsed.get(key)
        if isinstance(value, dict):
            merged.update({field: field_value for field, field_value in value.items() if field_value is not None})
            break
    merged["schema_version"] = fallback["schema_version"]
    merged["series_id"] = fallback["series_id"]
    return merged


def _normalize_episode_outline(
    series: Series,
    episode: Episode,
    source: dict[str, Any] | None,
    *,
    total_episodes: int,
    character_ids: list[str],
    scene_ids: list[str],
) -> dict[str, Any]:
    fallback = _episode_outline(
        series,
        episode,
        total_episodes=total_episodes,
        character_ids=character_ids,
        scene_ids=scene_ids,
    )
    if not isinstance(source, dict):
        return fallback

    normalized = dict(fallback)
    for key in (
        "title",
        "hook",
        "episode_goal",
        "central_conflict",
        "reversal",
        "cliffhanger",
        "previous_episode_handoff",
        "next_episode_handoff",
    ):
        value = source.get(key)
        if value is not None and (not isinstance(value, str) or value.strip() or key == "previous_episode_handoff"):
            normalized[key] = value

    for key in (
        "character_state_changes",
        "foreshadowing_introduced",
        "foreshadowing_resolved",
    ):
        value = source.get(key)
        if isinstance(value, list):
            normalized[key] = value

    for key, fallback_ids in (("character_ids", character_ids), ("scene_ids", scene_ids)):
        value = source.get(key)
        if isinstance(value, list):
            normalized[key] = [str(item) for item in value if item]
        elif fallback_ids:
            normalized[key] = fallback_ids

    for key in ("asset_usage", "generated_assets"):
        value = source.get(key)
        if isinstance(value, dict):
            normalized[key] = value

    normalized["schema_version"] = "series.episode_outline.v1"
    normalized["episode_number"] = int(episode.episode_number)
    if not normalized.get("title"):
        normalized["title"] = episode.title or f"Episode {episode.episode_number}"
    return normalized


def _normalize_and_scope_episode_outline(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    source: dict[str, Any] | None,
    total_episodes: int,
    character_ids: list[str],
    scene_ids: list[str],
    source_type: str,
) -> dict[str, Any]:
    scoped_character_ids = character_ids if _source_has_ids(source, "character_ids") else []
    scoped_scene_ids = scene_ids if _source_has_ids(source, "scene_ids") else []
    outline = _normalize_episode_outline(
        series,
        episode,
        source,
        total_episodes=total_episodes,
        character_ids=scoped_character_ids,
        scene_ids=scoped_scene_ids,
    )
    return normalize_episode_asset_scope(
        db,
        series,
        episode,
        outline,
        fallback_source=source_type or "episode_outline",
    )


def _source_has_ids(source: dict[str, Any] | None, key: str) -> bool:
    if not isinstance(source, dict):
        return False
    value = source.get(key)
    return isinstance(value, list) and any(str(item or "").strip() for item in value)


def _normalize_existing_episode_outline(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    artifact: Any,
) -> None:
    content = artifact.content_json if isinstance(artifact.content_json, dict) else {}
    normalized = normalize_episode_asset_scope(
        db,
        series,
        episode,
        content,
        fallback_source=artifact.source_type or "episode_outline",
    )
    if normalized == content:
        return
    artifact.content_json = normalized
    artifact.content_text = _content_text(normalized, "episode_goal", "hook", "title")
    flag_modified(artifact, "content_json")
    db.flush()


def _should_create_or_replace(artifact: Any | None, *, force: bool) -> bool:
    if artifact is None:
        return True
    return force or artifact.source_type in REPLACEABLE_SOURCE_TYPES


def _content_text(content: dict[str, Any], *preferred_keys: str) -> str:
    for key in preferred_keys:
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return json.dumps(content, ensure_ascii=False)


def _artifact_summary(artifact: Any) -> dict[str, Any]:
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


def _approved_story_artifact_summaries(
    service: AITextArtifactService,
    series: Series,
    episodes: list[Episode],
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for artifact_type in ("series_story_plan", "season_arc", "continuity_ledger"):
        artifact = service.latest_approved(
            target_type="series",
            target_id=series.id,
            artifact_type=artifact_type,
        )
        if artifact:
            artifacts.append(_artifact_summary(artifact))
    for episode in episodes:
        artifact = service.latest_approved(
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
        )
        if artifact:
            summary = _artifact_summary(artifact)
            summary["episode_number"] = int(episode.episode_number)
            artifacts.append(summary)
    return artifacts


def ensure_episode_placeholders(
    db: Session,
    series_id: str,
    *,
    commit: bool = True,
) -> EpisodePlaceholderResult:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")

    target = _target_episode_count(series)
    existing_rows = (
        db.query(Episode)
        .filter(Episode.series_id == series_id)
        .order_by(Episode.episode_number)
        .all()
    )
    existing_numbers = sorted(int(ep.episode_number) for ep in existing_rows)
    existing = set(existing_numbers)
    created: list[int] = []

    for episode_number in range(1, target + 1):
        if episode_number in existing:
            continue
        db.add(Episode(
            series_id=series_id,
            episode_number=episode_number,
            title=f"Episode {episode_number}",
            status="pending",
        ))
        created.append(episode_number)

    if created:
        if commit:
            db.commit()
        else:
            db.flush()

    return EpisodePlaceholderResult(
        series_id=series_id,
        target_episode_count=target,
        existing_episode_numbers=existing_numbers,
        created_episode_numbers=created,
    )


def ensure_series_continuity_artifacts(
    db: Session,
    series_id: str,
) -> ContinuityArtifactResult:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")

    episodes = (
        db.query(Episode)
        .filter(Episode.series_id == series_id)
        .order_by(Episode.episode_number)
        .all()
    )
    service = AITextArtifactService(db)
    character_ids = _ids_from_style_lock(series, "characters", "characters")
    scene_ids = _ids_from_style_lock(series, "scenes", "scenes")
    created_ledger = False
    created_outlines: list[int] = []

    if not service.latest_approved(
        target_type="series",
        target_id=series.id,
        artifact_type="continuity_ledger",
    ):
        ledger = service.create_artifact(
            series_id=series.id,
            target_type="series",
            target_id=series.id,
            artifact_type="continuity_ledger",
            source_type="system_backfill",
            input_json={"source": "ensure_episode_placeholders"},
            content_json=_continuity_ledger(
                series,
                episodes,
                character_ids=character_ids,
                scene_ids=scene_ids,
            ),
            content_text=series.logline or series.title,
            model_trace_json={"source": "ensure_episode_placeholders", "stage": "continuity_backfill"},
            created_by="system",
        )
        service.approve_artifact(ledger.id, actor_user_id="system")
        created_ledger = True

    total_episodes = _target_episode_count(series)
    for episode in episodes:
        if service.latest_approved(
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
        ):
            continue
        outline = _normalize_and_scope_episode_outline(
            db,
            series=series,
            episode=episode,
            source=None,
            total_episodes=total_episodes,
            character_ids=character_ids,
            scene_ids=scene_ids,
            source_type="system_backfill",
        )
        artifact = service.create_artifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
            source_type="system_backfill",
            input_json={"source": "ensure_episode_placeholders"},
            content_json=outline,
            content_text=outline["episode_goal"],
            model_trace_json={"source": "ensure_episode_placeholders", "stage": "episode_outline_backfill"},
            created_by="system",
        )
        service.approve_artifact(artifact.id, actor_user_id="system")
        created_outlines.append(int(episode.episode_number))

    return ContinuityArtifactResult(
        series_id=series_id,
        created_continuity_ledger=created_ledger,
        created_outline_episode_numbers=created_outlines,
    )


async def generate_series_story_plan(
    db: Session,
    series_id: str,
    force: bool = False,
) -> SeriesStoryPlanResult:
    placeholder_result = ensure_episode_placeholders(db, series_id)
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")

    target_episode_count = _target_episode_count(series)
    episodes = (
        db.query(Episode)
        .filter(Episode.series_id == series_id, Episode.episode_number <= target_episode_count)
        .order_by(Episode.episode_number)
        .all()
    )
    service = AITextArtifactService(db)
    character_ids = _ids_from_style_lock(series, "characters", "characters")
    scene_ids = _ids_from_style_lock(series, "scenes", "scenes")

    series_artifacts = {
        artifact_type: service.latest_approved(
            target_type="series",
            target_id=series.id,
            artifact_type=artifact_type,
        )
        for artifact_type in ("series_story_plan", "season_arc", "continuity_ledger")
    }
    outline_artifacts = {
        int(episode.episode_number): service.latest_approved(
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
        )
        for episode in episodes
    }

    needed_series_types = [
        artifact_type
        for artifact_type, artifact in series_artifacts.items()
        if _should_create_or_replace(artifact, force=force)
    ]
    outline_episodes_to_write = [
        episode
        for episode in episodes
        if _should_create_or_replace(outline_artifacts.get(int(episode.episode_number)), force=force)
    ]
    needs_generation = bool(needed_series_types or outline_episodes_to_write)
    source_type = "ai"
    parsed: dict[str, Any] = {}
    raw_output = ""
    model_trace: dict[str, Any] = {
        "stage": "story_planning",
        "stage_status": "preserved",
        "expert_id": "story_generator",
        "force": force,
    }

    if needs_generation:
        try:
            expert_result = await generate_story_plan_with_expert(
                db=db,
                series=series,
                episodes=episodes,
                character_ids=character_ids,
                scene_ids=scene_ids,
                existing_artifacts=_existing_artifact_context(service, series, episodes),
            )
            parsed = expert_result.parsed
            source_type = expert_result.source_type
            model_trace = dict(expert_result.model_trace)
            model_trace["force"] = force
        except Exception as exc:  # AI config, call, and parsing failures all fall back.
            source_type = "system_fallback"
            parsed = {}
            model_trace = {
                "stage": "story_planning",
                "stage_status": "fallback",
                "expert_id": "story_generator",
                "force": force,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

    story_plan = _merge_series_payload(
        _series_story_plan(series, episodes, character_ids=character_ids, scene_ids=scene_ids),
        parsed,
        "series_story_plan",
        "story_plan",
    )
    season_arc = _merge_series_payload(
        _season_arc(series, episodes),
        parsed,
        "season_arc",
        "arc",
    )
    continuity_ledger = _merge_series_payload(
        _continuity_ledger(series, episodes, character_ids=character_ids, scene_ids=scene_ids),
        parsed,
        "continuity_ledger",
        "ledger",
    )
    outline_sources = _episode_outline_sources(parsed)
    replaced_outline_episode_numbers: list[int] = []
    preserved_outline_episode_numbers: list[int] = []

    for artifact_type, content, text_keys in (
        ("series_story_plan", story_plan, ("summary", "season_promise", "logline")),
        ("season_arc", season_arc, ("arc_summary", "summary")),
        ("continuity_ledger", continuity_ledger, ("mainline", "summary")),
    ):
        existing = series_artifacts[artifact_type]
        if not _should_create_or_replace(existing, force=force):
            continue
        artifact = service.create_artifact(
            series_id=series.id,
            target_type="series",
            target_id=series.id,
            artifact_type=artifact_type,
            source_type=source_type,
            parent_artifact_id=existing.id if existing else None,
            input_json={"source": "generate_series_story_plan", "force": force},
            content_json=content,
            content_text=_content_text(content, *text_keys),
            model_trace_json=model_trace,
            created_by="system",
        )
        service.approve_artifact(artifact.id, actor_user_id="system")

    for episode in episodes:
        episode_number = int(episode.episode_number)
        existing = outline_artifacts.get(episode_number)
        if not _should_create_or_replace(existing, force=force):
            _normalize_existing_episode_outline(
                db,
                series=series,
                episode=episode,
                artifact=existing,
            )
            preserved_outline_episode_numbers.append(episode_number)
            continue
        if existing is not None:
            replaced_outline_episode_numbers.append(episode_number)
        outline = _normalize_and_scope_episode_outline(
            db,
            series=series,
            episode=episode,
            source=outline_sources.get(episode_number),
            total_episodes=target_episode_count,
            character_ids=character_ids,
            scene_ids=scene_ids,
            source_type=source_type,
        )
        artifact = service.create_artifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
            source_type=source_type,
            parent_artifact_id=existing.id if existing else None,
            input_json={"source": "generate_series_story_plan", "force": force},
            content_json=outline,
            content_text=_content_text(outline, "episode_goal", "hook", "title"),
            model_trace_json=model_trace,
            created_by="system",
        )
        service.approve_artifact(artifact.id, actor_user_id="system")

    ensure_series_continuity_artifacts(db, series_id)
    artifacts = _approved_story_artifact_summaries(service, series, episodes)
    return SeriesStoryPlanResult(
        series_id=series_id,
        target_episode_count=target_episode_count,
        created_episode_numbers=placeholder_result.created_episode_numbers,
        replaced_outline_episode_numbers=replaced_outline_episode_numbers,
        preserved_outline_episode_numbers=preserved_outline_episode_numbers,
        artifacts=artifacts,
        model_trace=model_trace,
    )


def is_series_completed(db: Session, series_id: str) -> bool:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")

    episodes = db.query(Episode).filter(Episode.series_id == series_id).all()
    if len(episodes) < _target_episode_count(series):
        return False
    return bool(episodes) and all(ep.status in FINISHED_EPISODE_STATUSES for ep in episodes)


def next_episode_number(db: Session, series_id: str) -> int | None:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")

    episodes = db.query(Episode).filter(Episode.series_id == series_id).all()
    done_numbers = {
        int(ep.episode_number)
        for ep in episodes
        if ep.status in FINISHED_EPISODE_STATUSES
    }
    for episode_number in range(1, _target_episode_count(series) + 1):
        if episode_number not in done_numbers:
            return episode_number
    return None
