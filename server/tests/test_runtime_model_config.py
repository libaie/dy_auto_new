import pytest

from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.runtime_model_config import (
    RuntimeModelConfigError,
    resolve_runtime_model_config,
    redact_runtime_model_config,
)


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


def test_resolve_runtime_model_config_supports_multi_scene_model(db):
    model = AIModel(
        name="Bailian Qwen 3.7 Plus",
        model_type="llm",
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=encrypt("bailian-key"),
        model_name="qwen3.7-plus",
        enabled=True,
        config_json={
            "scene_key": "llm_agency_expert_review",
            "scene_keys": ["script_generation", "llm_agency_expert_review"],
            "protocol": "openai_chat_completions",
            "config_version": 9,
        },
    )
    db.add(model)
    db.commit()

    resolved = resolve_runtime_model_config(db, "script_generation")

    assert resolved["scene_key"] == "script_generation"
    assert resolved["provider"] == "bailian"
    assert resolved["model"] == "qwen3.7-plus"
    assert resolved["api_key"] == "bailian-key"
    assert resolved["config_version"] == 9


def test_resolve_runtime_model_config_rejects_explicit_model_without_scene(db):
    model = AIModel(
        name="Video Only Model",
        model_type="video",
        provider="wan",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        model_name="wan2.7-i2v",
        enabled=True,
        config_json={"scene_key": "video_rendering"},
    )
    db.add(model)
    db.commit()

    with pytest.raises(RuntimeModelConfigError, match="script_generation"):
        resolve_runtime_model_config(db, "script_generation", explicit_model_id=model.id)


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
