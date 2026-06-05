from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db_models import AIModel, ImageProductionPolicyVersion, ImageSelectionPreview
from app.main import app
from app.services.crypto import encrypt
from app.services.image_production_strategy_service import create_strategy
from app.services.image_selection_preview_service import create_selection_preview


client = TestClient(app)


def _seed_image_model(db, *, name, scene_key, capabilities, sort_order=0, provider_options_schema=None, config_extra=None):
    config_json = {
        "scene_key": scene_key,
        "scene_keys": [scene_key],
        "capabilities": capabilities,
        "limits": {"max_output_images": 4, "max_reference_images": 4},
        "provider_options_schema": provider_options_schema or {"watermark": {"type": "boolean"}},
        "config_version": 1,
    }
    if config_extra:
        config_json.update(config_extra)
    model = AIModel(
        name=name,
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret-key"),
        api_secret=encrypt("secret-secret"),
        model_name=f"mock-{uuid4().hex}",
        enabled=True,
        sort_order=sort_order,
        config_json=config_json,
    )
    db.add(model)
    db.commit()
    return model


def _strategy(db, **overrides):
    payload = {
        "slug": f"preview-{uuid4().hex}",
        "name": "Preview Strategy",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image"],
        "default_model_id": None,
        "fallback_model_ids": [],
        "common_parameters": {},
        "provider_options": {},
    }
    payload.update(overrides)
    return create_strategy(db, payload)


def _policy(db, policy_type, snapshot):
    row = ImageProductionPolicyVersion(
        policy_type=policy_type,
        name=f"{policy_type}-preview-{uuid4().hex}",
        version=1,
        snapshot_json=snapshot,
        status="active",
    )
    db.add(row)
    db.commit()
    return row


def _error_code(exc_info):
    return exc_info.value.detail["error_code"]


def test_selection_preview_selects_strategy_default_model_and_persists_preview(db):
    first = _seed_image_model(
        db,
        name="first-supported",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        sort_order=0,
    )
    default = _seed_image_model(
        db,
        name="strategy-default",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        sort_order=1,
    )
    strategy = _strategy(db, default_model_id=default.id)

    result = create_selection_preview(
        db,
        {
            "mode": "text_to_image",
            "destination_role": "storyboard_first_frame",
            "strategy_id": strategy.id,
            "strategy_version": strategy.version,
            "provider_options": {"watermark": True},
            "count": 1,
        },
        user_id="test-user-id",
    )

    preview = db.query(ImageSelectionPreview).one()
    assert result["ok"] is True
    assert result["selected_model"]["model_id"] == default.id
    assert result["selected_model"]["model_id"] != first.id
    assert result["selection_explanation"]["selected_reason"] == "strategy_default_model"
    assert preview.selected_model_id == default.id
    assert preview.response_json["selected_model"]["model_id"] == default.id


def test_selection_preview_returns_cost_capacity_and_review_gate(db):
    model = _seed_image_model(
        db,
        name="policy-preview",
        scene_key="image_generation",
        capabilities={"text_to_image_set": True},
    )
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2,
        "currency": "CNY",
        "confirmation_threshold": 3,
        "latency_seconds_per_image": 5,
    })
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 20,
        "queue_when_full": True,
    })
    review_policy = _policy(db, "review", {
        "manual_required_for": ["image_to_video_input"],
        "ai_required_for": [],
    })
    strategy = _strategy(
        db,
        destination_role="image_to_video_input",
        supported_modes=["text_to_image_set"],
        default_model_id=model.id,
        cost_policy_version_id=cost_policy.id,
        capacity_policy_version_id=capacity_policy.id,
        review_policy_version_id=review_policy.id,
    )

    result = create_selection_preview(
        db,
        {
            "mode": "text_to_image_set",
            "destination_role": "image_to_video_input",
            "strategy_id": strategy.id,
            "strategy_version": strategy.version,
            "count": 2,
        },
    )

    assert result["cost_estimate"]["amount"] == 4
    assert result["cost_estimate"]["requires_confirmation"] is True
    assert result["time_estimate"]["estimated_seconds"] == 10
    assert result["capacity"]["status"] == "available"
    assert result["capacity"]["admission_action"] == "submit_now"
    assert result["review_gate"]["manual_required"] is True


def test_selection_preview_cost_uses_model_cost_profile_over_policy(db):
    model = _seed_image_model(
        db,
        name="model-cost-profile",
        scene_key="image_generation",
        capabilities={"text_to_image_set": True},
        config_extra={
            "cost_profile": {
                "unit_cost": 3.5,
                "currency": "USD",
            },
        },
    )
    cost_policy = _policy(db, "cost", {
        "unit_cost": 1,
        "currency": "CNY",
        "confirmation_threshold": 5,
        "latency_seconds_per_image": 7,
    })
    strategy = _strategy(
        db,
        supported_modes=["text_to_image_set"],
        default_model_id=model.id,
        cost_policy_version_id=cost_policy.id,
    )

    result = create_selection_preview(db, {
        "mode": "text_to_image_set",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 2,
    })

    assert result["cost_estimate"]["amount"] == 7
    assert result["cost_estimate"]["currency"] == "USD"
    assert result["cost_estimate"]["units"] == {"images": 2, "unit_cost": 3.5}
    assert result["cost_estimate"]["policy_version_id"] == cost_policy.id
    assert result["time_estimate"]["estimated_seconds"] == 14


def test_selection_preview_records_rejected_candidates_for_unsupported_capability(db):
    rejected = _seed_image_model(
        db,
        name="wrong-capability",
        scene_key="image_generation",
        capabilities={"text_to_image": False},
        sort_order=0,
    )
    selected = _seed_image_model(
        db,
        name="right-capability",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        sort_order=1,
    )

    result = create_selection_preview(
        db,
        {
            "mode": "text_to_image",
            "destination_role": "storyboard_first_frame",
            "count": 1,
        },
    )

    explanation = result["selection_explanation"]
    assert result["selected_model"]["model_id"] == selected.id
    assert explanation["candidate_count"] == 2
    assert explanation["rejected_candidates"] == [
        {
            "model_id": rejected.id,
            "name": rejected.name,
            "provider": rejected.provider,
            "model_name": rejected.model_name,
            "reason": "capability_not_supported",
            "detail": "Model does not support image_generation/text_to_image.",
            "rescue_action": "Choose a model that supports this scene and capability.",
        }
    ]


def test_selection_preview_returns_fallback_candidates_from_strategy(db):
    primary = _seed_image_model(
        db,
        name="Primary Text",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )
    fallback = _seed_image_model(
        db,
        name="Fallback Edit",
        scene_key="image_editing",
        capabilities={"image_to_image": True},
    )
    second_fallback = _seed_image_model(
        db,
        name="Second Fallback Edit",
        scene_key="image_editing",
        capabilities={"image_to_image": True},
    )
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2,
        "currency": "CNY",
        "confirmation_threshold": 3,
        "latency_seconds_per_image": 5,
    })
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 20,
        "queue_when_full": True,
    })
    review_policy = _policy(db, "review", {
        "manual_required_for": ["image_to_video_input"],
        "ai_required_for": [],
    })
    strategy = _strategy(
        db,
        default_model_id=primary.id,
        fallback_model_ids=[fallback.id, second_fallback.id],
        supported_modes=["image_to_image"],
        destination_role="image_to_video_input",
        cost_policy_version_id=cost_policy.id,
        capacity_policy_version_id=capacity_policy.id,
        review_policy_version_id=review_policy.id,
    )

    result = create_selection_preview(db, {
        "mode": "image_to_image",
        "destination_role": "image_to_video_input",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "source": {"url": "https://cdn.example/source.png"},
        "provider_options": {},
        "count": 2,
    })

    assert result["selected_model"] is None
    assert result["error_code"] == "IMAGE_FALLBACK_REQUIRES_CONFIRMATION"
    assert result["preview_blocked"] is True
    assert result["confirmation_required"] is True
    assert result["cost_estimate"]["amount"] == 4
    assert result["cost_estimate"]["requires_confirmation"] is True
    assert result["cost_estimate"]["policy_version_id"] == cost_policy.id
    assert result["time_estimate"]["estimated_seconds"] == 10
    assert result["capacity"]["status"] == "available"
    assert result["capacity"]["admission_action"] == "submit_now"
    assert result["capacity"]["policy_version_id"] == capacity_policy.id
    assert result["review_gate"]["manual_required"] is True
    assert result["review_gate"]["policy_version_id"] == review_policy.id
    assert [candidate["model_id"] for candidate in result["fallback_candidates"]] == [fallback.id, second_fallback.id]
    assert result["rescue_actions"] == [
        {"type": "confirm_fallback_model", "label": "Use fallback model", "model_id": fallback.id},
        {"type": "confirm_fallback_model", "label": "Use fallback model", "model_id": second_fallback.id},
    ]
    assert result["selection_preview_id"] is None
    assert db.query(ImageSelectionPreview).count() == 0


@pytest.mark.parametrize("provider_options", [{"api_key": "leak"}, {"unknown_option": True}])
def test_selection_preview_rejects_protected_or_unknown_provider_options(db, provider_options):
    _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )

    with pytest.raises(HTTPException) as exc_info:
        create_selection_preview(
            db,
            {
                "mode": "text_to_image",
                "destination_role": "storyboard_first_frame",
                "provider_options": provider_options,
            },
        )

    assert exc_info.value.status_code == 400
    assert _error_code(exc_info) == "IMAGE_PROVIDER_OPTIONS_INVALID"


def test_selection_preview_rejects_protected_provider_option_even_when_schema_declares_it(db):
    _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        provider_options_schema={"api_key": {"type": "string"}},
    )

    with pytest.raises(HTTPException) as exc_info:
        create_selection_preview(
            db,
            {
                "mode": "text_to_image",
                "destination_role": "storyboard_first_frame",
                "provider_options": {"api_key": "leak"},
            },
        )

    assert exc_info.value.status_code == 400
    assert _error_code(exc_info) == "IMAGE_PROVIDER_OPTIONS_INVALID"


def test_selection_preview_rejects_nested_protected_provider_option(db):
    _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        provider_options_schema={"advanced": {"type": "object"}},
    )

    with pytest.raises(HTTPException) as exc_info:
        create_selection_preview(
            db,
            {
                "mode": "text_to_image",
                "destination_role": "storyboard_first_frame",
                "provider_options": {"advanced": {"apiKey": "leak"}},
            },
        )

    assert exc_info.value.status_code == 400
    assert _error_code(exc_info) == "IMAGE_PROVIDER_OPTIONS_INVALID"


def test_selection_preview_hash_changes_when_output_format_changes(db):
    _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )
    base_payload = {
        "mode": "text_to_image",
        "destination_role": "storyboard_first_frame",
        "count": 1,
    }

    first = create_selection_preview(db, {**base_payload, "output_format": "png"})
    second = create_selection_preview(db, {**base_payload, "output_format": "jpeg"})

    assert first["request_hash"] != second["request_hash"]


@pytest.mark.parametrize(
    ("field", "first_value", "second_value"),
    [
        ("prompt", "first prompt", "second prompt"),
        ("negative_prompt", "low quality", "blurred"),
        ("size", "1024x1024", "2048x2048"),
        ("response_format", "url", "b64_json"),
        ("watermark", True, False),
    ],
)
def test_selection_preview_hash_changes_when_generation_request_field_changes(
    db,
    field,
    first_value,
    second_value,
):
    _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )
    base_payload = {
        "mode": "text_to_image",
        "destination_role": "storyboard_first_frame",
        "count": 1,
    }

    first = create_selection_preview(db, {**base_payload, field: first_value})
    second = create_selection_preview(db, {**base_payload, field: second_value})

    assert first["request_hash"] != second["request_hash"]


def test_selection_preview_hash_changes_when_model_config_version_changes(db):
    model = _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )
    payload = {
        "mode": "text_to_image",
        "destination_role": "storyboard_first_frame",
        "count": 1,
    }

    first = create_selection_preview(db, payload)
    model.config_json = {**(model.config_json or {}), "config_version": 2}
    db.commit()
    second = create_selection_preview(db, payload)

    assert first["request_hash"] != second["request_hash"]


def test_selection_preview_accepts_legacy_text_to_image_model_without_capabilities(db):
    model = AIModel(
        name="legacy",
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret-key"),
        model_name=f"mock-{uuid4().hex}",
        enabled=True,
        sort_order=0,
        config_json={
            "scene_key": "image_generation",
            "scene_keys": ["image_generation"],
            "provider_options_schema": {},
            "config_version": 1,
        },
    )
    db.add(model)
    db.commit()

    result = create_selection_preview(
        db,
        {
            "mode": "text_to_image",
            "destination_role": "storyboard_first_frame",
            "count": 1,
        },
    )

    assert result["selected_model"]["model_id"] == model.id


def test_selection_preview_rejects_stale_strategy_version(db):
    model = _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )
    strategy = _strategy(db, default_model_id=model.id)

    with pytest.raises(HTTPException) as exc_info:
        create_selection_preview(
            db,
            {
                "mode": "text_to_image",
                "destination_role": "storyboard_first_frame",
                "strategy_id": strategy.id,
                "strategy_version": strategy.version - 1,
            },
        )

    assert exc_info.value.status_code == 409
    assert _error_code(exc_info) == "IMAGE_STRATEGY_VERSION_CONFLICT"


def test_selection_preview_rejects_non_active_strategy(db):
    model = _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )
    strategy = _strategy(db, default_model_id=model.id)
    strategy.status = "disabled"
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        create_selection_preview(
            db,
            {
                "mode": "text_to_image",
                "destination_role": "storyboard_first_frame",
                "strategy_id": strategy.id,
                "strategy_version": strategy.version,
            },
        )

    assert exc_info.value.status_code == 409
    assert _error_code(exc_info) == "IMAGE_STRATEGY_ARCHIVED"


def test_selection_preview_endpoint_returns_preview_response(db):
    _seed_image_model(
        db,
        name="selected",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )

    resp = client.post(
        "/api/image-production/selection-preview",
        json={
            "mode": "text_to_image",
            "destination_role": "storyboard_first_frame",
            "count": 1,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["selection_preview_id"]
