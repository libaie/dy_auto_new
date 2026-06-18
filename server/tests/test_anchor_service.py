import pytest

from app.db_models import Character, Scene
from app.db_models import CharacterAnchor as CharacterAnchorRow
from app.db_models import SceneAnchor as SceneAnchorRow
from app.models.asset_anchor import AnchorReferenceMode


@pytest.mark.asyncio
async def test_ensure_character_anchor_reuses_existing_reference_slot(db, monkeypatch):
    from app.services import anchor_service
    from app.services.anchor_service import AssetAnchorManager

    async def unexpected_generate(*args, **kwargs):
        raise AssertionError("existing usable character reference should be reused")

    monkeypatch.setattr(anchor_service, "generate_reference_url", unexpected_generate)
    character = Character(
        name="Hero",
        role_type="protagonist",
        gender="female",
        age_range="25-30",
        appearance_desc="Clear oval face and shoulder-length black hair.",
        outfit_desc="Tailored white coat with a silver brooch.",
        avatar_front_url="https://cdn.test/existing-hero.png",
    )
    db.add(character)
    db.commit()

    anchor = await AssetAnchorManager(db).ensure_character_anchor(
        character.id,
        reference_slot="avatar_front_url",
        seed=42,
    )

    assert anchor.character_id == character.id
    assert anchor.name == "Hero"
    assert anchor.anchor_image_url == "https://cdn.test/existing-hero.png"
    assert anchor.seed == 42
    assert anchor.ref_mode == AnchorReferenceMode.CONTROLNET_FACE.value
    assert anchor.status == "locked"
    assert "Tailored white coat" in anchor.base_prompt


@pytest.mark.asyncio
async def test_ensure_scene_anchor_generates_missing_reference(db, monkeypatch):
    from app.services import anchor_service
    from app.services.anchor_service import AssetAnchorManager

    captured = {}

    async def fake_generate(db_arg, prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return "https://cdn.test/generated-scene.png"

    monkeypatch.setattr(anchor_service, "generate_reference_url", fake_generate)
    scene = Scene(
        name="Hotel Entrance",
        scene_type="outdoor",
        location_desc="Rainy luxury hotel entrance.",
        lighting="cold blue neon",
        mood="tense",
    )
    db.add(scene)
    db.commit()

    anchor = await AssetAnchorManager(db).ensure_scene_anchor(
        scene.id,
        reference_slot="reference_wideshot_url",
        seed=9001,
    )

    assert anchor.anchor_image_url == "https://cdn.test/generated-scene.png"
    assert anchor.scene_name == "Hotel Entrance"
    lowered_generation_prompt = captured["prompt"].lower()
    assert "empty environment plate" in lowered_generation_prompt
    assert "no people" in lowered_generation_prompt
    assert "no humans" in lowered_generation_prompt
    assert "no characters" in lowered_generation_prompt
    assert anchor.environment_prompt != captured["prompt"]
    assert "Keep environment layout" in anchor.environment_prompt
    assert captured["destination_role"] == "scene_reference_image"
    assert captured["destination_context"] == {
        "asset_type": "scene",
        "asset_id": scene.id,
        "anchor_kind": "scene_anchor",
        "slot": "reference_wideshot_url",
    }


def test_adapt_provider_parameters_maps_anchor_refs_and_filters_seed(db):
    from app.services.anchor_service import AssetAnchorManager

    character_anchor = CharacterAnchorRow(
        id="char-anchor-001",
        character_id="char-001",
        name="Hero",
        reference_slot="avatar_front_url",
        base_prompt="Stable hero face and white coat.",
        anchor_image_url="https://cdn.test/hero-anchor.png",
        seed=3001,
        ref_mode=AnchorReferenceMode.CONTROLNET_FACE.value,
        status="locked",
    )
    scene_anchor = SceneAnchorRow(
        id="scene-anchor-001",
        scene_id="scene-001",
        scene_name="Hotel Entrance",
        reference_slot="reference_wideshot_url",
        environment_prompt="Rainy hotel entrance.",
        anchor_image_url="https://cdn.test/scene-anchor.png",
        seed=9001,
        ref_mode=AnchorReferenceMode.IMAGE_TO_IMAGE.value,
        status="locked",
    )

    manager = AssetAnchorManager(db)
    payload = manager.adapt_provider_parameters(
        character_anchors=[character_anchor],
        scene_anchor=scene_anchor,
        provider="qwen-image",
        provider_options_schema={"seed": {"type": "number"}},
    )

    assert payload.provider_options == {"seed": 3001}
    assert payload.ref_image_url == "https://cdn.test/hero-anchor.png"
    assert payload.ref_mode == "controlnet_face"
    assert payload.reference_images == [
        {
            "url": "https://cdn.test/hero-anchor.png",
            "ref_image_url": "https://cdn.test/hero-anchor.png",
            "role": "character_anchor",
            "asset_type": "character",
            "asset_id": "char-001",
            "name": "Hero",
            "anchor_id": "char-anchor-001",
            "slot": "avatar_front_url",
            "ref_mode": "controlnet_face",
            "provider": "qwen-image",
            "priority": 1,
        },
        {
            "url": "https://cdn.test/scene-anchor.png",
            "ref_image_url": "https://cdn.test/scene-anchor.png",
            "role": "scene_reference",
            "asset_type": "scene",
            "asset_id": "scene-001",
            "name": "Hotel Entrance",
            "anchor_id": "scene-anchor-001",
            "slot": "reference_wideshot_url",
            "ref_mode": "image_to_image",
            "provider": "qwen-image",
            "priority": 2,
        },
    ]

    no_seed_payload = manager.adapt_provider_parameters(
        character_anchors=[character_anchor],
        scene_anchor=scene_anchor,
        provider="pixelle",
        provider_options_schema={},
    )
    assert no_seed_payload.provider_options == {}
