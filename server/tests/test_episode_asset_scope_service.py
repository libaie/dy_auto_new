import pytest

from app.db.models import Character, Episode, Scene, Series
from app.domains.ai_video_series.episode_asset_scope_service import (
    EpisodeAssetScopeError,
    normalize_episode_asset_scope,
)


def test_normalizes_existing_episode_asset_ids(db):
    series = Series(title="Family Ledger", total_episodes=1, status="draft")
    character = Character(name="Lin Xia", role_type="protagonist", gender="female")
    scene = Scene(name="Old Pharmacy", scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, episode])
    db.commit()

    outline = normalize_episode_asset_scope(
        db,
        series,
        episode,
        {
            "episode_number": 1,
            "title": "Receipt",
            "character_ids": [character.id, character.id],
            "scene_ids": [scene.id],
        },
    )

    assert outline["character_ids"] == [character.id]
    assert outline["scene_ids"] == [scene.id]
    assert outline["asset_usage"]["characters"][0]["source"] == "existing"
    assert outline["asset_usage"]["characters"][0]["name"] == "Lin Xia"
    assert outline["asset_usage"]["scenes"][0]["source"] == "existing"
    assert outline["asset_usage"]["scenes"][0]["name"] == "Old Pharmacy"


def test_creates_generated_assets_and_links_to_series(db):
    series = Series(title="Family Ledger", total_episodes=1, status="draft")
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, episode])
    db.commit()

    outline = normalize_episode_asset_scope(
        db,
        series,
        episode,
        {
            "episode_number": 1,
            "title": "Witness",
            "generated_assets": {
                "characters": [
                    {
                        "name": "Aunt Qiu",
                        "role_type": "supporting",
                        "gender": "female",
                        "age_range": "50-60",
                        "personality": "Keeps family secrets but cracks under pressure.",
                        "appearance_desc": "Short silver hair, tired eyes, careful posture.",
                        "outfit_desc": "Dark wool cardigan and jade bracelet.",
                        "usage": "Reveals the missing ledger.",
                    }
                ],
                "scenes": [
                    {
                        "name": "Rainy Bus Stop",
                        "scene_type": "outdoor",
                        "location_desc": "A narrow roadside stop under flickering lights.",
                        "lighting": "night",
                        "mood": "tense",
                        "usage": "Secret handoff location.",
                    }
                ],
            },
        },
    )
    db.refresh(series)

    assert len(outline["character_ids"]) == 1
    assert len(outline["scene_ids"]) == 1
    assert series.characters[0].name == "Aunt Qiu"
    assert series.scenes[0].name == "Rainy Bus Stop"
    assert series.characters[0].meta_json["source"] == "episode_story_planning"
    assert series.characters[0].meta_json["generated_for_episode_id"] == episode.id
    assert series.scenes[0].meta_json["source"] == "episode_story_planning"
    assert series.scenes[0].meta_json["generated_for_episode_id"] == episode.id
    assert outline["asset_usage"]["characters"][0]["source"] == "generated"
    assert outline["asset_usage"]["scenes"][0]["source"] == "generated"


def test_reuses_same_named_generated_assets_already_linked_to_series(db):
    series = Series(title="Family Ledger", total_episodes=1, status="draft")
    existing_character = Character(name="Aunt Qiu", role_type="supporting", gender="female")
    existing_scene = Scene(name="Rainy Bus Stop", scene_type="outdoor")
    series.characters.append(existing_character)
    series.scenes.append(existing_scene)
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, episode])
    db.commit()

    outline = normalize_episode_asset_scope(
        db,
        series,
        episode,
        {
            "episode_number": 1,
            "generated_assets": {
                "characters": [{"name": "Aunt Qiu", "role_type": "supporting", "usage": "Returns."}],
                "scenes": [{"name": "Rainy Bus Stop", "scene_type": "outdoor", "usage": "Returns."}],
            },
        },
    )

    assert outline["character_ids"] == [existing_character.id]
    assert outline["scene_ids"] == [existing_scene.id]
    assert db.query(Character).count() == 1
    assert db.query(Scene).count() == 1


def test_fallback_creates_minimal_assets_when_pool_is_empty(db):
    series = Series(title="Zero Pool", total_episodes=1, status="draft")
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, episode])
    db.commit()

    outline = normalize_episode_asset_scope(db, series, episode, {"episode_number": 1})
    db.refresh(series)

    assert outline["character_ids"] == [series.characters[0].id]
    assert outline["scene_ids"] == [series.scenes[0].id]
    assert series.characters[0].name == "Zero Pool 主角"
    assert series.scenes[0].name == "Zero Pool 主场景"
    assert outline["asset_usage"]["characters"][0]["source"] == "fallback"
    assert outline["asset_usage"]["scenes"][0]["source"] == "fallback"


def test_rejects_asset_ids_not_linked_to_series(db):
    series = Series(title="Owned", total_episodes=1, status="draft")
    other = Character(name="Other Series Lead", role_type="protagonist", gender="female")
    scene = Scene(name="Owned Room", scene_type="indoor")
    series.scenes.append(scene)
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, other, episode])
    db.commit()

    with pytest.raises(EpisodeAssetScopeError) as exc:
        normalize_episode_asset_scope(
            db,
            series,
            episode,
            {"episode_number": 1, "character_ids": [other.id], "scene_ids": [scene.id]},
        )

    assert exc.value.code == "EPISODE_ASSET_INVALID"
    assert exc.value.details["invalid_character_ids"] == [other.id]
