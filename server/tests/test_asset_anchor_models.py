import pytest
from pydantic import ValidationError
from sqlalchemy import inspect

from app.db.models import Character, Scene
from app.db.models import CharacterAnchor as CharacterAnchorRow
from app.db.models import SceneAnchor as SceneAnchorRow
from app.models.asset_anchor import AnchorReferenceMode, CharacterAnchor, SceneAnchor


def test_asset_anchor_pydantic_models_validate_seed_and_ref_mode():
    character_anchor = CharacterAnchor(
        character_id="char-001",
        name="Hero",
        base_prompt="Stable face, black suit, neat short hair.",
        anchor_image_url="https://cdn.test/char.png",
        seed=12345,
        ref_mode=AnchorReferenceMode.CONTROLNET_FACE,
    )
    scene_anchor = SceneAnchor(
        scene_id="scene-001",
        scene_name="Hotel Entrance",
        environment_prompt="Rainy luxury hotel entrance, cold blue neon.",
        anchor_image_url="https://cdn.test/scene.png",
        ref_mode=AnchorReferenceMode.IMAGE_TO_IMAGE,
    )

    assert character_anchor.seed == 12345
    assert character_anchor.name == "Hero"
    assert character_anchor.ref_mode == AnchorReferenceMode.CONTROLNET_FACE
    assert scene_anchor.scene_name == "Hotel Entrance"
    assert scene_anchor.ref_mode == AnchorReferenceMode.IMAGE_TO_IMAGE

    with pytest.raises(ValidationError, match="greater than or equal"):
        CharacterAnchor(
            character_id="char-001",
            name="Hero",
            base_prompt="Stable face.",
            seed=-1,
        )


def test_asset_anchor_tables_include_lock_contract_columns(test_db):
    inspector = inspect(test_db)
    character_columns = {col["name"] for col in inspector.get_columns("character_anchors")}
    scene_columns = {col["name"] for col in inspector.get_columns("scene_anchors")}
    character_fks = {
        tuple(fk["constrained_columns"]): fk["referred_table"]
        for fk in inspector.get_foreign_keys("character_anchors")
    }
    scene_fks = {
        tuple(fk["constrained_columns"]): fk["referred_table"]
        for fk in inspector.get_foreign_keys("scene_anchors")
    }

    assert {
        "character_id",
        "name",
        "reference_slot",
        "base_prompt",
        "anchor_image_url",
        "seed",
        "ref_mode",
        "provider_options_json",
        "status",
        "metadata_json",
    }.issubset(character_columns)
    assert {
        "scene_id",
        "scene_name",
        "reference_slot",
        "environment_prompt",
        "anchor_image_url",
        "seed",
        "ref_mode",
        "provider_options_json",
        "status",
        "metadata_json",
    }.issubset(scene_columns)
    assert character_fks[("character_id",)] == "characters"
    assert scene_fks[("scene_id",)] == "scenes"


def test_asset_anchor_sqlalchemy_roundtrip(db):
    character = Character(
        name="Hero",
        role_type="protagonist",
        gender="female",
        appearance_desc="Clear oval face and shoulder-length black hair.",
        outfit_desc="Tailored white coat.",
    )
    scene = Scene(
        name="Hotel Entrance",
        scene_type="outdoor",
        location_desc="Rainy luxury hotel entrance.",
        lighting="cold blue neon",
        mood="tense",
    )
    db.add_all([character, scene])
    db.flush()

    db.add(CharacterAnchorRow(
        character_id=character.id,
        name=character.name,
        reference_slot="avatar_front_url",
        base_prompt="Clear oval face, shoulder-length black hair, tailored white coat.",
        anchor_image_url="https://cdn.test/hero-anchor.png",
        seed=3001,
        ref_mode="controlnet_face",
        status="locked",
        provider_options_json={"locked": True},
    ))
    db.add(SceneAnchorRow(
        scene_id=scene.id,
        scene_name=scene.name,
        reference_slot="reference_wideshot_url",
        environment_prompt="Rainy luxury hotel entrance, cold blue neon, tense mood.",
        anchor_image_url="https://cdn.test/scene-anchor.png",
        seed=9001,
        ref_mode="image_to_image",
        status="locked",
        provider_options_json={"locked": True},
    ))
    db.commit()

    saved_character = db.query(CharacterAnchorRow).filter_by(character_id=character.id).one()
    saved_scene = db.query(SceneAnchorRow).filter_by(scene_id=scene.id).one()
    assert saved_character.name == "Hero"
    assert saved_character.seed == 3001
    assert saved_scene.scene_name == "Hotel Entrance"
    assert saved_scene.seed == 9001
