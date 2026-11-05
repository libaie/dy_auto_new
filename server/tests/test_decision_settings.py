"""Decision credentials stay server-side and config edits are validated atomically."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db_models import SystemSetting
from app.services import crypto


@pytest.fixture(autouse=True)
def isolated_decision_settings(db, monkeypatch):
    for name in (
        "DECISION_ENABLED", "DECISION_API_KEY", "DECISION_API_URL", "DECISION_MODEL",
        "DECISION_MIN_CONFIDENCE", "DECISION_MIN_PROBABILITY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ENCRYPTION_KEY", "decision-settings-test-encryption-only")
    monkeypatch.setattr(crypto, "_cipher", None)
    db.query(SystemSetting).filter(SystemSetting.key.startswith("decision_")).delete()
    db.commit()
    yield
    db.query(SystemSetting).filter(SystemSetting.key.startswith("decision_")).delete()
    db.commit()


@pytest.fixture
def client():
    return TestClient(app)


def test_decision_key_is_encrypted_and_only_masked_over_http(client, db):
    secret = "test-only-decision-credential"
    response = client.put("/api/settings", json={"settings": {
        "decision_api_key": secret,
        "decision_enabled": "true",
    }})
    assert response.status_code == 200
    stored = db.query(SystemSetting).filter_by(key="decision_api_key").one().value
    assert stored != secret
    assert crypto.decrypt(stored) == secret
    response = client.get("/api/settings")
    assert response.json()["decision_api_key"] == "****"
    assert secret not in response.text
    assert stored not in response.text


@pytest.mark.parametrize("placeholder", ["", "  ", "****"])
def test_blank_or_masked_decision_key_preserves_saved_credential(client, db, placeholder):
    encrypted = crypto.encrypt("test-only-existing-credential")
    db.add(SystemSetting(key="decision_api_key", value=encrypted))
    db.commit()
    response = client.put("/api/settings", json={"settings": {
        "decision_api_key": placeholder,
        "decision_enabled": "false",
    }})
    assert response.status_code == 200
    db.expire_all()
    assert db.query(SystemSetting).filter_by(key="decision_api_key").one().value == encrypted
    assert client.get("/api/settings").json()["decision_enabled"] == "false"


def test_effective_env_decision_settings_are_visible_without_secret(client, monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_API_KEY", "test-only-environment-credential")
    monkeypatch.setenv("DECISION_MIN_PROBABILITY", "0.8")
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["decision_enabled"] == "true"
    assert data["decision_api_key"] == "****"
    assert data["decision_api_url"] == "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
    assert data["decision_model"] == "typesafe-ai/jev"
    assert float(data["decision_min_probability"]) == 0.8
    assert "test-only-environment-credential" not in response.text


@pytest.mark.parametrize("enabled,expected", [
    ("true", "true"), ("false", "false"), ("unknown", "true"),
])
@pytest.mark.parametrize("environment_key", ["", "test-only-environment-credential"])
def test_invalid_env_threshold_preserves_effective_recovery_settings(
    client, db, monkeypatch, enabled, expected, environment_key,
):
    monkeypatch.setenv("DECISION_ENABLED", enabled)
    monkeypatch.setenv("DECISION_MIN_CONFIDENCE", "nan")
    monkeypatch.setenv("DECISION_MIN_PROBABILITY", "0.9")
    monkeypatch.setenv("DECISION_API_KEY", environment_key)

    response = client.get("/api/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["decision_config_error"]
    assert data["decision_enabled"] == expected
    assert float(data["decision_min_probability"]) == 0.9
    assert data["decision_api_key"] == ("****" if environment_key else "")
    assert data["decision_api_url"] == "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
    assert data["decision_model"] == "typesafe-ai/jev"
    assert "test-only-environment-credential" not in response.text
    assert db.query(SystemSetting).filter(SystemSetting.key.startswith("decision_")).count() == 0


@pytest.mark.parametrize("enabled,environment_enabled", [("true", "false"), ("false", "true")])
def test_recovery_preserves_database_overrides_and_masks_existing_key(
    client, db, monkeypatch, enabled, environment_enabled,
):
    monkeypatch.setenv("DECISION_ENABLED", environment_enabled)
    monkeypatch.setenv("DECISION_MIN_CONFIDENCE", "nan")
    monkeypatch.setenv("DECISION_MIN_PROBABILITY", "0.9")
    monkeypatch.setenv("DECISION_API_KEY", "test-only-environment-credential")
    stored_key = crypto.encrypt("test-only-stored-credential")
    db.add_all([
        SystemSetting(key="decision_enabled", value=enabled),
        SystemSetting(key="decision_min_probability", value="0.95"),
        SystemSetting(key="decision_api_key", value=stored_key),
    ])
    db.commit()

    response = client.get("/api/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["decision_config_error"]
    assert data["decision_enabled"] == enabled
    assert float(data["decision_min_probability"]) == 0.95
    assert data["decision_api_key"] == "****"
    assert data["decision_api_url"] == "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
    assert data["decision_model"] == "typesafe-ai/jev"
    assert "test-only-environment-credential" not in response.text
    assert "test-only-stored-credential" not in response.text
    assert stored_key not in response.text


@pytest.mark.parametrize("key,value", [
    ("decision_min_probability", "nan"),
    ("decision_min_confidence", "1.1"),
    ("decision_enabled", "maybe"),
    ("decision_model", "deepseek-chat"),
    ("decision_api_url", "https://example.com/typesafe/v1/systemone"),
    ("decision_api_url", "https://ai-gateway.vercel.sh/typesafe/v1/systemone/chat/completions"),
])
def test_invalid_decision_update_cannot_partially_save_other_fields(client, db, key, value):
    db.add(SystemSetting(key="decision_min_probability", value="0.75"))
    db.commit()
    response = client.put("/api/settings", json={"settings": {
        "decision_min_probability": "0.8",
        "decision_api_key": "test-only-rejected-credential",
        key: value,
    }})
    assert response.status_code == 422
    assert "test-only-rejected-credential" not in response.text
    db.expire_all()
    assert db.query(SystemSetting).filter_by(key="decision_min_probability").one().value == "0.75"
    assert db.query(SystemSetting).filter_by(key="decision_api_key").first() is None


def test_new_key_requires_explicit_server_encryption_key(client, db, monkeypatch):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    response = client.put("/api/settings", json={"settings": {
        "decision_api_key": "test-only-do-not-save-with-default-cipher",
    }})
    assert response.status_code == 503
    assert "ENCRYPTION_KEY" in response.json()["detail"]
    assert "test-only-do-not-save-with-default-cipher" not in response.text
    assert db.query(SystemSetting).filter_by(key="decision_api_key").first() is None


def test_decision_key_write_still_requires_admin(client, real_auth):
    response = client.put("/api/settings", json={"settings": {
        "decision_api_key": "test-only-unauthorized-credential",
    }})
    assert response.status_code in (401, 403)
