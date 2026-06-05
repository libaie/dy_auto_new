from uuid import uuid4

from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.image_model_selection_service import resolve_image_model_selection
from app.services.image_production_strategy_service import create_strategy


def _seed_image_model(
    db,
    *,
    name,
    scene_key="image_generation",
    scene_keys=None,
    capabilities=None,
    enabled=True,
    sort_order=0,
    model_name=None,
):
    model = AIModel(
        name=name,
        provider="seedance",
        model_type="image",
        base_url="https://example.invalid",
        api_key=encrypt("secret-key"),
        model_name=model_name or f"seedance-{uuid4().hex}",
        enabled=enabled,
        sort_order=sort_order,
        config_json={
            "config_version": 1,
            "scene_key": scene_key,
            "scene_keys": scene_keys or [scene_key],
            "capabilities": capabilities or {},
            "provider_options_schema": {"watermark": {"type": "boolean"}},
        },
    )
    db.add(model)
    db.commit()
    return model


def _strategy(db, **overrides):
    payload = {
        "slug": f"model-selection-{uuid4().hex}",
        "name": "Model Selection Strategy",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["image_to_image"],
        "default_model_id": None,
        "fallback_model_ids": [],
        "common_parameters": {},
        "provider_options": {},
    }
    payload.update(overrides)
    return create_strategy(db, payload)


def test_selection_diagnostics_selects_first_supported_model(db):
    unsupported = _seed_image_model(
        db,
        name="text-only",
        capabilities={"text_to_image": True, "image_to_image": False},
        sort_order=0,
        model_name="seedance-text-only",
    )
    supported = _seed_image_model(
        db,
        name="image-capable",
        capabilities={"image_to_image": True},
        sort_order=1,
        model_name="seedance-image-capable",
    )

    result = resolve_image_model_selection(
        db,
        scene_key="image_generation",
        capability_key="image_to_image",
    )

    assert result["selected_model"]["model_id"] == supported.id
    assert result["selected_reason"] == "first_supported_model"
    assert result["candidate_count"] == 2
    assert result["rejected_candidates"] == [
        {
            "model_id": unsupported.id,
            "name": "text-only",
            "provider": "seedance",
            "model_name": "seedance-text-only",
            "reason": "capability_not_supported",
            "detail": "Model does not support image_generation/image_to_image.",
            "rescue_action": "Choose a model that supports this scene and capability.",
        }
    ]


def test_selection_diagnostics_rejects_disabled_and_non_preferred_models(db):
    disabled = _seed_image_model(
        db,
        name="disabled",
        capabilities={"image_to_image": True},
        enabled=False,
        sort_order=0,
        model_name="seedance-disabled",
    )
    non_preferred = _seed_image_model(
        db,
        name="non-preferred",
        capabilities={"image_to_image": True},
        sort_order=1,
        model_name="seedance-non-preferred",
    )
    requested = _seed_image_model(
        db,
        name="requested",
        capabilities={"image_to_image": True},
        sort_order=2,
        model_name="seedance-requested",
    )

    result = resolve_image_model_selection(
        db,
        scene_key="image_generation",
        capability_key="image_to_image",
        requested_model_id=requested.id,
    )

    assert result["selected_model"]["model_id"] == requested.id
    assert result["selected_reason"] == "requested_model"
    assert {candidate["model_id"]: candidate["reason"] for candidate in result["rejected_candidates"]} == {
        disabled.id: "disabled",
        non_preferred.id: "not_preferred_model",
    }


def test_selection_diagnostics_returns_fallback_candidates_for_strategy(db):
    default = _seed_image_model(
        db,
        name="unsupported-default",
        capabilities={"text_to_image": True, "image_to_image": False},
        sort_order=0,
        model_name="seedance-unsupported-default",
    )
    fallback = _seed_image_model(
        db,
        name="supported-fallback",
        capabilities={"image_to_image": True},
        sort_order=1,
        model_name="seedance-supported-fallback",
    )
    strategy = _strategy(db, default_model_id=default.id, fallback_model_ids=[fallback.id])

    result = resolve_image_model_selection(
        db,
        scene_key="image_generation",
        capability_key="image_to_image",
        strategy=strategy,
    )

    assert result["selected_model"] is None
    assert result["selected_reason"] is None
    assert result["fallback_candidates"] == [
        {
            "model_id": fallback.id,
            "name": "supported-fallback",
            "provider": "seedance",
            "model_name": "seedance-supported-fallback",
            "risk_labels": ["requires_manual_confirmation"],
        }
    ]
    assert "fallback_requires_confirmation" in result["warnings"]
    assert result["rescue_actions"] == [
        {
            "type": "confirm_fallback_model",
            "label": "Use fallback model",
            "model_id": fallback.id,
        }
    ]
