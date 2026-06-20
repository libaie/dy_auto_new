import pytest

from app.db.models import (
    Character,
    Episode,
    PipelineRun,
    ProductionPlan,
    Scene,
    Series,
    VideoCollection,
    VideoProductionAsset,
    VideoProductionRun,
    series_characters,
    series_scenes,
)
from app.domains.creative_library.asset_lifecycle_service import (
    AssetLifecycleError,
    archive_character_or_scene,
    delete_or_archive_series,
    unlink_character_from_series,
    unlink_scene_from_series,
)


def _series(db, title="Lifecycle"):
    series = Series(title=title, logline="test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    return series, episode


def _video_asset(db, series, episode, metadata=None):
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="draft",
        current_stage="draft",
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-1",
        asset_type="image",
        stage="image_generation",
        metadata_json=metadata or {},
    )
    db.add(asset)
    db.flush()
    return asset


def test_delete_or_archive_series_hard_deletes_empty_series(db):
    series, episode = _series(db)
    character = Character(name="Lead")
    scene = Scene(name="Room")
    db.add_all([character, scene])
    db.flush()
    db.execute(series_characters.insert().values(series_id=series.id, character_id=character.id))
    db.execute(series_scenes.insert().values(series_id=series.id, scene_id=scene.id))
    db.commit()
    series_id = series.id
    episode_id = episode.id
    character_id = character.id
    scene_id = scene.id

    result = delete_or_archive_series(db, series_id)

    assert result == {"action": "deleted"}
    assert db.query(Series).filter(Series.id == series_id).first() is None
    assert db.query(Episode).filter(Episode.id == episode_id).first() is None
    assert db.execute(series_characters.select()).first() is None
    assert db.execute(series_scenes.select()).first() is None
    assert db.query(Character).filter(Character.id == character_id).first() is not None
    assert db.query(Scene).filter(Scene.id == scene_id).first() is not None


@pytest.mark.parametrize("dependency", [
    "video_run",
    "pipeline_run",
    "video_url",
    "asset",
    "production_plan",
    "video_collection",
])
def test_delete_or_archive_series_archives_when_production_dependency_exists(db, dependency):
    series, episode = _series(db)
    if dependency == "video_run":
        db.add(VideoProductionRun(series_id=series.id, episode_id=episode.id, status="draft", current_stage="draft"))
    elif dependency == "pipeline_run":
        db.add(PipelineRun(series_id=series.id, episode_id=episode.id, status="running"))
    elif dependency == "video_url":
        episode.video_url = "https://cdn.test/final.mp4"
    elif dependency == "asset":
        _video_asset(db, series, episode)
    elif dependency == "production_plan":
        db.add(ProductionPlan(series_id=series.id))
    elif dependency == "video_collection":
        db.add(VideoCollection(series_id=series.id))
    db.commit()

    result = delete_or_archive_series(db, series.id)

    assert result == {"action": "archived"}
    db.refresh(series)
    assert series.status == "archived"
    assert db.query(Episode).filter(Episode.id == episode.id).first() is not None


def test_unlink_character_and_scene_from_series(db):
    series, _episode = _series(db)
    character = Character(name="Lead")
    scene = Scene(name="Room")
    db.add_all([character, scene])
    db.flush()
    db.execute(series_characters.insert().values(series_id=series.id, character_id=character.id))
    db.execute(series_scenes.insert().values(series_id=series.id, scene_id=scene.id))
    db.commit()

    assert unlink_character_from_series(db, series.id, character.id) == {"action": "unlinked"}
    assert unlink_scene_from_series(db, series.id, scene.id) == {"action": "unlinked"}

    assert db.execute(series_characters.select()).first() is None
    assert db.execute(series_scenes.select()).first() is None


def test_unlink_missing_asset_raises_not_found(db):
    series, _episode = _series(db)
    db.commit()

    with pytest.raises(AssetLifecycleError) as exc_info:
        unlink_character_from_series(db, series.id, "missing")

    assert exc_info.value.code == "ASSET_NOT_FOUND"


def test_archive_referenced_character_sets_meta_json_archived(db):
    series, episode = _series(db)
    character = Character(name="Lead")
    db.add(character)
    db.flush()
    series.story_bible_json = {"style_lock": {"characters": [{"id": character.id}]}}
    episode.storyboard_json = {"frames": [{"character_id": character.id}]}
    db.commit()

    result = archive_character_or_scene(db, "character", character.id)

    assert result == {"action": "archived"}
    db.refresh(character)
    assert character.meta_json["archived"] is True
    assert character.meta_json["archived_at"]


def test_archive_referenced_scene_sets_meta_json_archived_from_asset_metadata(db):
    series, episode = _series(db)
    scene = Scene(name="Room")
    db.add(scene)
    db.flush()
    _video_asset(db, series, episode, metadata={"scene_refs": [scene.id]})
    db.commit()

    result = archive_character_or_scene(db, "scene", scene.id)

    assert result == {"action": "archived"}
    db.refresh(scene)
    assert scene.meta_json["archived"] is True
    assert scene.meta_json["archived_at"]


def test_archive_unreferenced_character_or_scene_hard_deletes(db):
    character = Character(name="Standalone")
    scene = Scene(name="Standalone Room")
    db.add_all([character, scene])
    db.commit()
    character_id = character.id
    scene_id = scene.id

    assert archive_character_or_scene(db, "character", character_id) == {"action": "deleted"}
    assert archive_character_or_scene(db, "scene", scene_id) == {"action": "deleted"}

    assert db.query(Character).filter(Character.id == character_id).first() is None
    assert db.query(Scene).filter(Scene.id == scene_id).first() is None


def test_archive_unsupported_asset_type_raises_error(db):
    with pytest.raises(AssetLifecycleError) as exc_info:
        archive_character_or_scene(db, "prop", "asset-1")

    assert exc_info.value.code == "ASSET_TYPE_UNSUPPORTED"
