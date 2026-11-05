"""Decision settings resolve independently and never disclose gateway credentials."""
import pytest

from app.db_models import SystemSetting
from app.services import crypto


@pytest.fixture(autouse=True)
def isolated_decision_settings(db, monkeypatch):
    db.query(SystemSetting).delete()
    db.commit()
    for name in (
        "DECISION_ENABLED", "DECISION_API_KEY", "DECISION_API_URL", "DECISION_MODEL",
        "DECISION_MIN_CONFIDENCE", "DECISION_MIN_PROBABILITY", "AI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ENCRYPTION_KEY", "decision-config-test-encryption")
    monkeypatch.setattr(crypto, "_cipher", None)
    yield
    db.query(SystemSetting).delete()
    db.commit()


def set_settings(db, **values):
    for key, value in values.items():
        db.add(SystemSetting(key=key, value=value))
    db.commit()


def test_default_off_does_not_borrow_generation_credentials(db, monkeypatch):
    from app.services.decision_config import resolve_decision_config

    monkeypatch.setenv("AI_API_KEY", "generation-only-env")
    set_settings(db, llm_api_key="generation-only-db")
    assert resolve_decision_config(db) == {
        "enabled": False,
        "api_key": "",
        "api_url": "https://ai-gateway.vercel.sh/typesafe/v1/systemone",
        "model": "typesafe-ai/jev",
        "min_confidence": 0.5,
        "min_probability": 0.75,
    }


def test_environment_key_is_plaintext_and_enabled_survives_missing_key(db, monkeypatch):
    from app.services.decision_config import resolve_decision_config

    monkeypatch.setenv("DECISION_ENABLED", "true")
    assert resolve_decision_config(db)["enabled"] is True
    assert resolve_decision_config(db)["api_key"] == ""
    monkeypatch.setenv("DECISION_API_KEY", "dedicated-env-key")
    assert resolve_decision_config(db)["api_key"] == "dedicated-env-key"


def test_database_overrides_environment_including_false_and_zero(db, monkeypatch):
    from app.services.decision_config import resolve_decision_config

    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_API_KEY", "env-key")
    monkeypatch.setenv("DECISION_MIN_CONFIDENCE", "0.8")
    set_settings(
        db, decision_enabled="false", decision_api_key=crypto.encrypt("stored-key"),
        decision_min_confidence="0", decision_min_probability="1",
    )
    resolved = resolve_decision_config(db)
    assert resolved["enabled"] is False
    assert resolved["api_key"] == "stored-key"
    assert resolved["min_confidence"] == 0
    assert resolved["min_probability"] == 1


def test_empty_database_key_does_not_fall_back_to_environment(db, monkeypatch):
    from app.services.decision_config import resolve_decision_config

    monkeypatch.setenv("DECISION_API_KEY", "env-key")
    set_settings(db, decision_api_key="")
    assert resolve_decision_config(db)["api_key"] == ""


def test_admin_view_masks_unreadable_key_without_decrypting(db):
    from app.services.decision_config import get_decision_settings

    set_settings(db, decision_enabled="true", decision_api_key="unreadable-secret")
    assert get_decision_settings(db) == {
        "decision_enabled": "true",
        "decision_api_key": "****",
        "decision_api_url": "https://ai-gateway.vercel.sh/typesafe/v1/systemone",
        "decision_model": "typesafe-ai/jev",
        "decision_min_confidence": "0.5",
        "decision_min_probability": "0.75",
    }


@pytest.mark.parametrize("enabled, expected", [("true", True), ("false", False)])
def test_public_config_never_exposes_key_and_preserves_enabled_on_key_failure(db, enabled, expected):
    from app.services.decision_config import get_public_decision_config, resolve_decision_config

    set_settings(db, decision_enabled=enabled, decision_api_key="unreadable-secret")
    public = get_public_decision_config(db)
    assert public == {
        "enabled": expected, "model": "typesafe-ai/jev",
        "min_confidence": 0.5, "min_probability": 0.75,
    }
    with pytest.raises(ValueError) as error:
        resolve_decision_config(db)
    assert "unreadable-secret" not in str(error.value)


@pytest.mark.parametrize("enabled, expected", [("true", True), ("false", False), ("broken", True)])
def test_public_config_fails_closed_when_nonsecret_configuration_is_invalid(db, enabled, expected):
    from app.services.decision_config import get_public_decision_config

    set_settings(db, decision_enabled=enabled, decision_min_confidence="NaN")
    assert get_public_decision_config(db) == {
        "enabled": expected, "model": "typesafe-ai/jev",
        "min_confidence": 0.5, "min_probability": 0.75,
    }


def test_settings_view_includes_effective_environment_defaults_without_credentials(db, monkeypatch):
    from app.services.decision_config import get_decision_settings

    monkeypatch.setenv("DECISION_API_KEY", "private-env-key")
    monkeypatch.setenv("DECISION_MIN_PROBABILITY", "0.9")
    settings = get_decision_settings(db)
    assert settings["decision_api_key"] == "****"
    assert settings["decision_min_probability"] == "0.9"
    assert "private-env-key" not in repr(settings)


@pytest.mark.parametrize("key, value", [
    ("decision_enabled", "sometimes"),
    ("decision_min_confidence", "NaN"),
    ("decision_min_confidence", "Infinity"),
    ("decision_min_probability", "-0.1"),
    ("decision_min_probability", "1.1"),
    ("decision_min_probability", True),
    ("decision_model", "generation-model"),
    ("decision_api_url", "https://attacker.invalid/collect?key=secret-marker"),
    ("decision_api_url", "https://ai-gateway.vercel.sh/typesafe/v1/systemone/"),
    ("decision_api_key", "secret-marker\r\nInjected: header"),
])
def test_settings_validation_rejects_invalid_configuration_without_echoing_inputs(key, value):
    from app.services.decision_config import validate_decision_settings

    with pytest.raises(ValueError) as error:
        validate_decision_settings({key: value})
    assert "secret-marker" not in str(error.value)
    assert "attacker.invalid" not in str(error.value)


def test_settings_validation_accepts_partial_settings_and_key_preservation_markers():
    from app.services.decision_config import validate_decision_settings

    validate_decision_settings({"decision_enabled": "true", "unrelated": object()})
    validate_decision_settings({"decision_api_key": ""})
    validate_decision_settings({"decision_api_key": "****"})
    validate_decision_settings({"decision_min_confidence": "0", "decision_min_probability": "1"})
