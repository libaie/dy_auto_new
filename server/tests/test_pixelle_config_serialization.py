import uuid

from app.db.models import AIModel
from app.domains.pixelle_integration.pixelle_router import _serialize_ai_models
from app.domains.system_configuration.crypto import encrypt


def _seed_model(db, **kwargs):
    model = AIModel(
        id=kwargs.pop("id", str(uuid.uuid4())),
        name=kwargs.pop("name", "Pixelle Model"),
        model_type=kwargs.pop("model_type", "image"),
        provider=kwargs.pop("provider", "seedance"),
        base_url=kwargs.pop("base_url", "https://ark.cn-beijing.volces.com/api/plan/v3"),
        api_key=encrypt(kwargs.pop("api_key", "pixelle-key")),
        model_name=kwargs.pop("model_name", f"pixelle-{uuid.uuid4()}"),
        enabled=kwargs.pop("enabled", True),
        config_json=kwargs.pop("config_json", {"scene_key": "image_generation"}),
        **kwargs,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def test_serialize_ai_models_exports_all_scene_keys_for_multi_scene_model(db):
    _seed_model(
        db,
        model_name="doubao-seedream-5.0-lite",
        config_json={
            "scene_key": "image_generation",
            "scene_keys": ["image_generation", "image_editing"],
        },
    )

    serialized = _serialize_ai_models(db)

    assert set(serialized["scenes"]) == {"image_generation", "image_editing"}
    assert serialized["scenes"]["image_generation"]["model"] == "doubao-seedream-5.0-lite"
    assert serialized["scenes"]["image_editing"]["model"] == "doubao-seedream-5.0-lite"


def test_serialize_ai_models_keeps_single_scene_model_behavior(db):
    _seed_model(
        db,
        model_name="seedance-video",
        model_type="video",
        config_json={"scene_key": "video_rendering"},
    )

    serialized = _serialize_ai_models(db)

    assert set(serialized["scenes"]) == {"video_rendering"}
    assert serialized["scenes"]["video_rendering"]["model"] == "seedance-video"


def test_serialize_ai_models_uses_first_model_for_duplicate_scene(db):
    _seed_model(
        db,
        name="Lower Sort",
        model_name="first-image-editing",
        sort_order=0,
        config_json={
            "scene_key": "image_generation",
            "scene_keys": ["image_generation", "image_editing"],
        },
    )
    _seed_model(
        db,
        name="Higher Sort",
        model_name="second-image-editing",
        sort_order=10,
        config_json={
            "scene_key": "image_editing",
            "scene_keys": ["image_editing"],
        },
    )

    serialized = _serialize_ai_models(db)

    assert serialized["scenes"]["image_editing"]["model"] == "first-image-editing"
