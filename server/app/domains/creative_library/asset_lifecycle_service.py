from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import bj_now
from app.db.models.creative_library import Character, Scene
from app.db.models.video_production import VideoCollection
from app.db_models import (
    Episode,
    PipelineRun,
    ProductionPlan,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    series_characters,
    series_scenes,
)


@dataclass
class AssetLifecycleError(Exception):
    code: str
    message: str
    details: dict | None = None


def _json_contains(value, needle: str) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value == needle
    if isinstance(value, dict):
        return any(_json_contains(v, needle) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_json_contains(v, needle) for v in value)
    return False


def _series_episode_ids(db: Session, series_id: str) -> list[str]:
    return [
        row[0]
        for row in db.query(Episode.id).filter(Episode.series_id == series_id).all()
    ]


def _series_has_production_dependencies(db: Session, series_id: str) -> bool:
    if db.query(VideoProductionRun.id).filter(VideoProductionRun.series_id == series_id).first():
        return True
    if db.query(PipelineRun.id).filter(PipelineRun.series_id == series_id).first():
        return True
    if db.query(ProductionPlan.id).filter(ProductionPlan.series_id == series_id).first():
        return True
    if db.query(VideoCollection.id).filter(VideoCollection.series_id == series_id).first():
        return True
    if db.query(Episode.id).filter(
        Episode.series_id == series_id,
        Episode.video_url.isnot(None),
        Episode.video_url != "",
    ).first():
        return True
    episode_ids = _series_episode_ids(db, series_id)
    if episode_ids and db.query(VideoProductionAsset.id).filter(
        VideoProductionAsset.episode_id.in_(episode_ids)
    ).first():
        return True
    return False


def delete_or_archive_series(db: Session, series_id: str) -> dict:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise AssetLifecycleError("SERIES_NOT_FOUND", "Series not found", {"series_id": series_id})

    if _series_has_production_dependencies(db, series_id):
        series.status = "archived"
        db.commit()
        return {"action": "archived"}

    db.execute(series_characters.delete().where(series_characters.c.series_id == series_id))
    db.execute(series_scenes.delete().where(series_scenes.c.series_id == series_id))
    db.query(Episode).filter(Episode.series_id == series_id).delete(synchronize_session=False)
    db.delete(series)
    db.commit()
    return {"action": "deleted"}


def unlink_character_from_series(db: Session, series_id: str, character_id: str) -> dict:
    if not db.query(Series.id).filter(Series.id == series_id).first():
        raise AssetLifecycleError("SERIES_NOT_FOUND", "Series not found", {"series_id": series_id})
    if not db.query(Character.id).filter(Character.id == character_id).first():
        raise AssetLifecycleError("ASSET_NOT_FOUND", "Character not found", {"character_id": character_id})

    result = db.execute(
        series_characters.delete().where(
            series_characters.c.series_id == series_id,
            series_characters.c.character_id == character_id,
        )
    )
    if result.rowcount == 0:
        raise AssetLifecycleError("ASSET_NOT_FOUND", "Character is not linked to series", {
            "series_id": series_id,
            "character_id": character_id,
        })
    db.commit()
    return {"action": "unlinked"}


def unlink_scene_from_series(db: Session, series_id: str, scene_id: str) -> dict:
    if not db.query(Series.id).filter(Series.id == series_id).first():
        raise AssetLifecycleError("SERIES_NOT_FOUND", "Series not found", {"series_id": series_id})
    if not db.query(Scene.id).filter(Scene.id == scene_id).first():
        raise AssetLifecycleError("ASSET_NOT_FOUND", "Scene not found", {"scene_id": scene_id})

    result = db.execute(
        series_scenes.delete().where(
            series_scenes.c.series_id == series_id,
            series_scenes.c.scene_id == scene_id,
        )
    )
    if result.rowcount == 0:
        raise AssetLifecycleError("ASSET_NOT_FOUND", "Scene is not linked to series", {
            "series_id": series_id,
            "scene_id": scene_id,
        })
    db.commit()
    return {"action": "unlinked"}


def _character_is_referenced(db: Session, character_id: str) -> bool:
    if db.execute(
        series_characters.select().where(series_characters.c.character_id == character_id)
    ).first():
        return True
    return _json_references_asset(db, character_id)


def _scene_is_referenced(db: Session, scene_id: str) -> bool:
    if db.execute(series_scenes.select().where(series_scenes.c.scene_id == scene_id)).first():
        return True
    return _json_references_asset(db, scene_id)


def _json_references_asset(db: Session, asset_id: str) -> bool:
    for (story_bible_json,) in db.query(Series.story_bible_json).all():
        if _json_contains(story_bible_json, asset_id):
            return True
    for (storyboard_json,) in db.query(Episode.storyboard_json).all():
        if _json_contains(storyboard_json, asset_id):
            return True
    for (metadata_json,) in db.query(VideoProductionAsset.metadata_json).all():
        if _json_contains(metadata_json, asset_id):
            return True
    return False


def archive_character_or_scene(db: Session, asset_type: str, asset_id: str) -> dict:
    if asset_type == "character":
        row = db.query(Character).filter(Character.id == asset_id).first()
        is_referenced = _character_is_referenced
        json_column = "meta_json"
    elif asset_type == "scene":
        row = db.query(Scene).filter(Scene.id == asset_id).first()
        is_referenced = _scene_is_referenced
        json_column = "meta_json"
    else:
        raise AssetLifecycleError("ASSET_TYPE_UNSUPPORTED", "Unsupported asset type", {"asset_type": asset_type})

    if not row:
        raise AssetLifecycleError("ASSET_NOT_FOUND", "Asset not found", {"asset_type": asset_type, "asset_id": asset_id})

    if is_referenced(db, asset_id):
        meta_json = dict(row.meta_json or {})
        meta_json["archived"] = True
        meta_json["archived_at"] = bj_now().isoformat()
        row.meta_json = meta_json
        flag_modified(row, json_column)
        db.commit()
        return {"action": "archived"}

    db.delete(row)
    db.commit()
    return {"action": "deleted"}
