from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.runtime_model_config import resolve_runtime_model_config, redact_runtime_model_config


def test_resolve_runtime_model_config_decrypts_for_server_payload(db):
    model = AIModel(
        name="Seedance Image",
        model_type="image",
        provider="seedance",
        base_url="https://ark.test",
        api_key=encrypt("secret-key"),
        model_name="doubao-seedance-image",
        enabled=True,
        config_json={"scene_key": "image_generation", "config_version": 7},
    )
    db.add(model)
    db.commit()

    resolved = resolve_runtime_model_config(db, "image_generation")

    assert resolved["scene_key"] == "image_generation"
    assert resolved["provider"] == "seedance"
    assert resolved["model"] == "doubao-seedance-image"
    assert resolved["api_key"] == "secret-key"
    assert resolved["config_version"] == 7


def test_redact_runtime_model_config_removes_secret():
    payload = {
        "scene_key": "image_generation",
        "provider": "seedance",
        "model": "doubao-seedance-image",
        "api_key": "secret-key",
        "base_url": "https://ark.test",
        "config_version": 7,
    }

    redacted = redact_runtime_model_config(payload)

    assert redacted["provider"] == "seedance"
    assert redacted["model"] == "doubao-seedance-image"
    assert redacted["config_version"] == 7
    assert "api_key" not in redacted
