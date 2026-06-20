import uuid

import pytest

from app.db.models import AIModel
from app.domains.system_configuration.crypto import encrypt
from app.domains.model_configuration.runtime_model_config import (
    RuntimeModelConfigError,
    resolve_image_model_for_capability,
)


BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"


def _seed_image_model(db, **kwargs):
    scene_key = kwargs.pop("scene_key", "image_editing")
    capabilities = kwargs.pop("capabilities", {})
    config_json = kwargs.pop("config_json", {
        "scene_key": scene_key,
        "scene_keys": kwargs.pop("scene_keys", [scene_key]),
        "capabilities": capabilities,
        "config_version": kwargs.pop("config_version", 1),
    })
    model = AIModel(
        id=kwargs.pop("id", str(uuid.uuid4())),
        name=kwargs.pop("name", "Seedream test"),
        model_type="image",
        provider="seedance",
        base_url=kwargs.pop("base_url", BASE_URL),
        api_key=encrypt(kwargs.pop("api_key", "seedream-key")),
        model_name=kwargs.pop("model_name", f"seedream-{uuid.uuid4()}"),
        enabled=kwargs.pop("enabled", True),
        sort_order=kwargs.pop("sort_order", 0),
        config_json=config_json,
        **kwargs,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def test_resolver_selects_supported_image_to_image_model(db):
    _seed_image_model(
        db,
        name="Unsupported first",
        sort_order=0,
        capabilities={"text_to_image": True, "image_to_image": False},
    )
    supported = _seed_image_model(
        db,
        name="Supported second",
        sort_order=1,
        capabilities={"image_to_image": True},
    )

    resolved = resolve_image_model_for_capability(db, "image_editing", "image_to_image")

    assert resolved["model_id"] == supported.id
    assert resolved["scene_key"] == "image_editing"
    assert resolved["capability_key"] == "image_to_image"


def test_explicit_unsupported_model_raises(db):
    model = _seed_image_model(
        db,
        capabilities={"image_to_image": False},
    )

    with pytest.raises(RuntimeModelConfigError, match="IMAGE_CAPABILITY_UNSUPPORTED"):
        resolve_image_model_for_capability(
            db,
            "image_editing",
            "image_to_image",
            explicit_model_id=model.id,
        )


def test_legacy_image_generation_model_without_capabilities_supports_text_to_image(db):
    model = _seed_image_model(
        db,
        scene_key="image_generation",
        config_json={"scene_key": "image_generation", "config_version": 3},
    )

    resolved = resolve_image_model_for_capability(db, "image_generation", "text_to_image")

    assert resolved["model_id"] == model.id
    assert resolved["capability_key"] == "text_to_image"


def test_single_seedream_model_supports_generation_and_editing_capabilities(db):
    model = _seed_image_model(
        db,
        scene_key="image_generation",
        scene_keys=["image_generation", "image_editing"],
        capabilities={
            "text_to_image": True,
            "image_to_image": True,
            "multi_reference_to_image_set": True,
        },
    )

    generated = resolve_image_model_for_capability(db, "image_generation", "text_to_image")
    edited = resolve_image_model_for_capability(db, "image_editing", "image_to_image")
    image_set = resolve_image_model_for_capability(db, "image_editing", "multi_reference_to_image_set")

    assert generated["model_id"] == model.id
    assert edited["model_id"] == model.id
    assert image_set["model_id"] == model.id


def test_seed_ai_models_union_merges_seedream_scene_keys(db):
    from app.domains.model_configuration.ai_models_router import SEEDANCE_ARK_BASE_URL, SEEDREAM_IMAGE_MODEL, seed_ai_models

    model = _seed_image_model(
        db,
        name="Existing Seedream",
        model_name=SEEDREAM_IMAGE_MODEL,
        scene_key="image_generation",
        config_json={
            "scene_key": "image_generation",
            "scene_keys": ["image_generation"],
            "default_size": "2048x2048",
            "limits": {"aspect_ratio_range": [1, 2]},
        },
        base_url=SEEDANCE_ARK_BASE_URL,
    )

    seed_ai_models(db)
    db.refresh(model)

    assert model.config_json["scene_keys"] == ["image_generation", "image_editing"]
    assert model.config_json["default_size"] == "2048x2048"
    assert model.config_json["limits"]["aspect_ratio_range"] == [1, 2]
