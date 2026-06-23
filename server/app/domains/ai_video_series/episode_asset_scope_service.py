"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 episode_asset_scope_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.ai_video_series import Episode, Series
from app.db.models.creative_library import Character, Scene


GENERATED_ASSET_SOURCE = "episode_story_planning"


@dataclass
class EpisodeAssetScopeError(ValueError):
    """业务类：承载 EpisodeAssetScopeError 相关的数据结构、状态或业务协作。

    类参数：code、details、message 承载该类的业务配置、状态或数据字段。
    """
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """业务函数：处理 __str__ 对应的业务流程、校验或数据转换。

        入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        return self.message


def normalize_episode_asset_scope(
    db: Session,
    series: Series,
    episode: Episode,
    outline: dict[str, Any] | None,
    *,
    fallback_source: str = "episode_outline",
) -> dict[str, Any]:
    """业务函数：处理 normalize_episode_asset_scope 对应的业务流程、校验或数据转换。

    入参：db、series、episode、outline、fallback_source 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    normalized = dict(outline or {})
    generated_assets = normalized.get("generated_assets")
    if not isinstance(generated_assets, dict):
        generated_assets = {}

    usage_by_character_id = _usage_by_id(normalized.get("asset_usage"), "characters")
    usage_by_scene_id = _usage_by_id(normalized.get("asset_usage"), "scenes")
    source_by_character_id: dict[str, str] = {}
    source_by_scene_id: dict[str, str] = {}

    generated_character_ids = _create_generated_characters(
        db,
        series,
        episode,
        generated_assets.get("characters") or [],
        usage_by_character_id,
        source_by_character_id,
    )
    generated_scene_ids = _create_generated_scenes(
        db,
        series,
        episode,
        generated_assets.get("scenes") or [],
        usage_by_scene_id,
        source_by_scene_id,
    )
    db.flush()

    character_ids = _dedupe_strings(normalized.get("character_ids"))
    scene_ids = _dedupe_strings(normalized.get("scene_ids"))
    if not character_ids:
        character_ids = generated_character_ids
    if not scene_ids:
        scene_ids = generated_scene_ids

    if not character_ids:
        fallback_character = _fallback_character(db, series, episode)
        db.flush()
        character_ids = [fallback_character.id]
        source_by_character_id[fallback_character.id] = "fallback"
    if not scene_ids:
        fallback_scene = _fallback_scene(db, series, episode)
        db.flush()
        scene_ids = [fallback_scene.id]
        source_by_scene_id[fallback_scene.id] = "fallback"

    characters = _validate_characters(db, series, character_ids)
    scenes = _validate_scenes(db, series, scene_ids)

    normalized["character_ids"] = [character.id for character in characters]
    normalized["scene_ids"] = [scene.id for scene in scenes]
    normalized["asset_usage"] = {
        "characters": [
            _character_usage(
                character,
                source_by_character_id.get(character.id, "existing"),
                usage_by_character_id.get(character.id),
                fallback_source,
            )
            for character in characters
        ],
        "scenes": [
            _scene_usage(
                scene,
                source_by_scene_id.get(scene.id, "existing"),
                usage_by_scene_id.get(scene.id),
                fallback_source,
            )
            for scene in scenes
        ],
    }
    normalized["generated_assets"] = {
        "characters": list(generated_assets.get("characters") or []),
        "scenes": list(generated_assets.get("scenes") or []),
    }
    return normalized


def _dedupe_strings(value: Any) -> list[str]:
    """业务函数：处理 _dedupe_strings 对应的业务流程、校验或数据转换。

    入参：value 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        values = []
    return list(dict.fromkeys(str(item).strip() for item in values if str(item or "").strip()))


def _usage_by_id(asset_usage: Any, key: str) -> dict[str, str]:
    """业务函数：处理 _usage_by_id 对应的业务流程、校验或数据转换。

    入参：asset_usage、key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not isinstance(asset_usage, dict):
        return {}
    values = asset_usage.get(key)
    if not isinstance(values, list):
        return {}
    result: dict[str, str] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("id") or "").strip()
        usage = str(item.get("usage") or "").strip()
        if asset_id and usage:
            result[asset_id] = usage
    return result


def _series_characters(series: Series) -> list[Character]:
    """业务函数：处理 _series_characters 对应的业务流程、校验或数据转换。

    入参：series 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return list(series.characters or [])


def _series_scenes(series: Series) -> list[Scene]:
    """业务函数：处理 _series_scenes 对应的业务流程、校验或数据转换。

    入参：series 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return list(series.scenes or [])


def dedupe_asset_ids(value: Any) -> list[str]:
    return _dedupe_strings(value)


def linked_series_characters(series: Series) -> list[Character]:
    return _series_characters(series)


def linked_series_scenes(series: Series) -> list[Scene]:
    return _series_scenes(series)


def _find_series_character_by_name(series: Series, name: str) -> Character | None:
    """业务函数：处理 _find_series_character_by_name 对应的业务流程、校验或数据转换。

    入参：series、name 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    normalized_name = name.strip().casefold()
    if not normalized_name:
        return None
    for character in _series_characters(series):
        if (character.name or "").strip().casefold() == normalized_name:
            return character
    return None


def _find_series_scene_by_name(series: Series, name: str) -> Scene | None:
    """业务函数：处理 _find_series_scene_by_name 对应的业务流程、校验或数据转换。

    入参：series、name 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    normalized_name = name.strip().casefold()
    if not normalized_name:
        return None
    for scene in _series_scenes(series):
        if (scene.name or "").strip().casefold() == normalized_name:
            return scene
    return None


def _create_generated_characters(
    db: Session,
    series: Series,
    episode: Episode,
    specs: list[Any],
    usage_by_id: dict[str, str],
    source_by_id: dict[str, str],
) -> list[str]:
    """业务函数：处理 _create_generated_characters 对应的业务流程、校验或数据转换。

    入参：db、series、episode、specs、usage_by_id、source_by_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    ids: list[str] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name") or "").strip()
        if not name:
            continue
        character = _find_series_character_by_name(series, name)
        if character is None:
            character = Character(
                name=name,
                role_type=str(spec.get("role_type") or "supporting")[:20],
                gender=str(spec.get("gender") or "unknown")[:10],
                age_range=str(spec.get("age_range") or "")[:20],
                personality=str(spec.get("personality") or ""),
                appearance_desc=str(spec.get("appearance_desc") or ""),
                outfit_desc=str(spec.get("outfit_desc") or ""),
                meta_json=_generated_meta(episode),
            )
            db.add(character)
            series.characters.append(character)
            db.flush()
            source_by_id[character.id] = "generated"
        ids.append(character.id)
        usage = str(spec.get("usage") or "").strip()
        if usage:
            usage_by_id[character.id] = usage
    return list(dict.fromkeys(ids))


def _create_generated_scenes(
    db: Session,
    series: Series,
    episode: Episode,
    specs: list[Any],
    usage_by_id: dict[str, str],
    source_by_id: dict[str, str],
) -> list[str]:
    """业务函数：处理 _create_generated_scenes 对应的业务流程、校验或数据转换。

    入参：db、series、episode、specs、usage_by_id、source_by_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    ids: list[str] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name") or "").strip()
        if not name:
            continue
        scene = _find_series_scene_by_name(series, name)
        if scene is None:
            scene = Scene(
                name=name,
                scene_type=str(spec.get("scene_type") or "indoor")[:20],
                location_desc=str(spec.get("location_desc") or ""),
                lighting=str(spec.get("lighting") or "")[:50],
                mood=str(spec.get("mood") or "")[:50],
                meta_json=_generated_meta(episode),
            )
            db.add(scene)
            series.scenes.append(scene)
            db.flush()
            source_by_id[scene.id] = "generated"
        ids.append(scene.id)
        usage = str(spec.get("usage") or "").strip()
        if usage:
            usage_by_id[scene.id] = usage
    return list(dict.fromkeys(ids))


def _generated_meta(episode: Episode) -> dict[str, str]:
    """业务函数：处理 _generated_meta 对应的业务流程、校验或数据转换。

    入参：episode 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "source": GENERATED_ASSET_SOURCE,
        "generated_for_episode_id": episode.id,
    }


def _fallback_character(db: Session, series: Series, episode: Episode) -> Character:
    """业务函数：处理 _fallback_character 对应的业务流程、校验或数据转换。

    入参：db、series、episode 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    existing = _series_characters(series)
    if existing:
        return sorted(
            existing,
            key=lambda character: (
                0 if character.role_type == "protagonist" else 1,
                str(character.created_at or ""),
                character.name or "",
                character.id or "",
            ),
        )[0]
    character = Character(
        name=f"{series.title} 主角",
        role_type="protagonist",
        gender="unknown",
        age_range="",
        personality="系列核心人物，承担本集主要剧情推进。",
        appearance_desc="适合系列主角的稳定视觉形象。",
        outfit_desc="与系列类型一致的常用服装。",
        meta_json=_generated_meta(episode),
    )
    db.add(character)
    series.characters.append(character)
    return character


def _fallback_scene(db: Session, series: Series, episode: Episode) -> Scene:
    """业务函数：处理 _fallback_scene 对应的业务流程、校验或数据转换。

    入参：db、series、episode 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    existing = _series_scenes(series)
    if existing:
        return sorted(
            existing,
            key=lambda scene: (
                str(scene.created_at or ""),
                scene.name or "",
                scene.id or "",
            ),
        )[0]
    scene = Scene(
        name=f"{series.title} 主场景",
        scene_type="indoor",
        location_desc="支撑本集主要剧情冲突的核心场景。",
        lighting="neutral",
        mood="dramatic",
        meta_json=_generated_meta(episode),
    )
    db.add(scene)
    series.scenes.append(scene)
    return scene


def _validate_characters(db: Session, series: Series, ids: list[str]) -> list[Character]:
    """业务函数：处理 _validate_characters 对应的业务流程、校验或数据转换。

    入参：db、series、ids 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    linked_ids = {character.id for character in _series_characters(series)}
    found = {character.id: character for character in db.query(Character).filter(Character.id.in_(ids)).all()}
    invalid_ids = [asset_id for asset_id in ids if asset_id not in found or asset_id not in linked_ids]
    if invalid_ids:
        raise EpisodeAssetScopeError(
            code="EPISODE_ASSET_INVALID",
            message="Episode character IDs must exist and be linked to the series.",
            details={"invalid_character_ids": invalid_ids},
        )
    return [found[asset_id] for asset_id in ids]


def _validate_scenes(db: Session, series: Series, ids: list[str]) -> list[Scene]:
    """业务函数：处理 _validate_scenes 对应的业务流程、校验或数据转换。

    入参：db、series、ids 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    linked_ids = {scene.id for scene in _series_scenes(series)}
    found = {scene.id: scene for scene in db.query(Scene).filter(Scene.id.in_(ids)).all()}
    invalid_ids = [asset_id for asset_id in ids if asset_id not in found or asset_id not in linked_ids]
    if invalid_ids:
        raise EpisodeAssetScopeError(
            code="EPISODE_ASSET_INVALID",
            message="Episode scene IDs must exist and be linked to the series.",
            details={"invalid_scene_ids": invalid_ids},
        )
    return [found[asset_id] for asset_id in ids]


def _character_usage(
    character: Character,
    source: str,
    usage: str | None,
    fallback_source: str,
) -> dict[str, str]:
    """业务函数：处理 _character_usage 对应的业务流程、校验或数据转换。

    入参：character、source、usage、fallback_source 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "id": character.id,
        "name": character.name,
        "usage": usage or _default_usage(character.name, fallback_source),
        "source": source,
    }


def _scene_usage(
    scene: Scene,
    source: str,
    usage: str | None,
    fallback_source: str,
) -> dict[str, str]:
    """业务函数：处理 _scene_usage 对应的业务流程、校验或数据转换。

    入参：scene、source、usage、fallback_source 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "id": scene.id,
        "name": scene.name,
        "usage": usage or _default_usage(scene.name, fallback_source),
        "source": source,
    }


def _default_usage(name: str, fallback_source: str) -> str:
    """业务函数：处理 _default_usage 对应的业务流程、校验或数据转换。

    入参：name、fallback_source 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return f"{name} 由 {fallback_source} 纳入本集资产作用域。"
