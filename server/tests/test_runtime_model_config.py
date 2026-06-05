from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.runtime_model_config import resolve_runtime_model_config, redact_runtime_model_config


def test_resolve_runtime_model_config_decrypts_for_server_payload(db):
    model = AIModel(
        name="Seedream 5.0 Lite",
        model_type="image",
        provider="seedance",
        base_url="https://ark.test",
        api_key=encrypt("secret-key"),
        model_name="doubao-seedream-5.0-lite",
        enabled=True,
        config_json={"scene_key": "image_generation", "config_version": 7},
    )
    db.add(model)
    db.commit()

    resolved = resolve_runtime_model_config(db, "image_generation")

    assert resolved["scene_key"] == "image_generation"
    assert resolved["provider"] == "seedance"
    assert resolved["model"] == "doubao-seedream-5.0-lite"
    assert resolved["api_key"] == "secret-key"
    assert resolved["config_version"] == 7


def test_resolve_runtime_model_config_supports_agency_expert_review_scene(db):
    model = AIModel(
        name="Expert Review LLM",
        model_type="llm",
        provider="openai-compatible",
        base_url="https://llm.test/v1",
        api_key=encrypt("expert-key"),
        model_name="expert-review-model",
        enabled=True,
        config_json={
            "scene_key": "llm_agency_expert_review",
            "protocol": "openai_chat_completions",
            "config_version": 3,
            "max_tokens": 2048,
            "temperature": 0.2,
        },
    )
    db.add(model)
    db.commit()

    resolved = resolve_runtime_model_config(db, "llm_agency_expert_review")

    assert resolved["scene_key"] == "llm_agency_expert_review"
    assert resolved["provider"] == "openai-compatible"
    assert resolved["base_url"] == "https://llm.test/v1"
    assert resolved["model"] == "expert-review-model"
    assert resolved["api_key"] == "expert-key"
    assert resolved["config"]["protocol"] == "openai_chat_completions"


def test_redact_runtime_model_config_removes_secret():
    payload = {
        "scene_key": "image_generation",
        "provider": "seedance",
        "model": "doubao-seedream-5.0-lite",
        "api_key": "secret-key",
        "base_url": "https://ark.test",
        "config_version": 7,
    }

    redacted = redact_runtime_model_config(payload)

    assert redacted["provider"] == "seedance"
    assert redacted["model"] == "doubao-seedream-5.0-lite"
    assert redacted["config_version"] == 7
    assert "api_key" not in redacted
