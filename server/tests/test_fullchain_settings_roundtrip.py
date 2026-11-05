"""The settings form must edit the configuration that model callers actually use."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import config
from app.database import get_db
from app.db_models import SystemSetting
from app.main import app


@pytest.fixture(autouse=True)
def isolated_settings(db, monkeypatch):
    db.query(SystemSetting).delete()
    db.commit()
    monkeypatch.setenv("AI_API_KEY", "synthetic-environment-key")
    monkeypatch.setenv("AI_BASE_URL", "https://generation.example.test")
    monkeypatch.setenv("AI_MODEL", "generation-model")
    monkeypatch.setenv("AI_THINKING", "disabled")
    monkeypatch.setattr(config, "PIXELLE_VIDEO_URL", "http://synthetic-video:8500")
    monkeypatch.setattr(config, "PIXELLE_VIDEO_TIMEOUT", 720)
    yield
    db.rollback()
    db.query(SystemSetting).delete()
    db.commit()


@pytest.mark.parametrize("source", ["environment", "ai", "llm"])
def test_enabling_decisions_preserves_effective_generation_settings(db, source):
    if source != "environment":
        for suffix, value in {
            "api_key": "synthetic-stored-key", "base_url": "https://generation.example.test",
            "model": "generation-model", "thinking": "disabled",
        }.items():
            db.add(SystemSetting(key=source + "_" + suffix, value=value))
        db.commit()

    client = TestClient(app)
    loaded = client.get("/api/settings")
    assert loaded.status_code == 200
    values = loaded.json()
    assert values["ai_model"] == "generation-model"
    assert values["ai_base_url"] == "https://generation.example.test"
    assert values["ai_thinking"] == "disabled"
    assert values["ai_api_key"] == "****"
    assert "synthetic-environment-key" not in loaded.text
    assert "synthetic-stored-key" not in loaded.text
    assert values["pixelle_video_url"] == "http://synthetic-video:8500"
    assert int(values["pixelle_video_timeout"]) == 720

    payload = {key: values[key] for key in (
        "ai_model", "ai_base_url", "ai_thinking", "pixelle_video_url", "pixelle_video_timeout",
    )}
    payload["decision_enabled"] = "true"
    saved = client.put("/api/settings", json={"settings": payload})
    assert saved.status_code == 200, saved.text
    db.expire_all()
    actual = config.get_ai_config_with_key(db)
    assert actual["model"] == "generation-model"
    assert actual["api_url"] == "https://generation.example.test/v1/chat/completions"
    assert actual["thinking_enabled"] is False


def test_settings_edit_updates_the_generation_values_that_shadow_legacy_keys(db):
    for suffix, value in {
        "api_key": "synthetic-old-key", "model": "old-model",
        "base_url": "https://old.example.test", "thinking": "max",
    }.items():
        db.add(SystemSetting(key="llm_" + suffix, value=value))
    db.commit()
    response = TestClient(app).put("/api/settings", json={"settings": {
        "ai_api_key": "synthetic-replacement-key", "ai_model": "replacement-model",
        "ai_base_url": "https://replacement.example.test", "ai_thinking": "disabled",
    }})
    assert response.status_code == 200, response.text
    db.expire_all()
    actual = config.get_ai_config_with_key(db)
    assert actual["model"] == "replacement-model"
    assert actual["api_key"] == "synthetic-replacement-key"
    assert actual["api_url"] == "https://replacement.example.test/v1/chat/completions"
    assert actual["thinking_enabled"] is False


@pytest.mark.parametrize("reason", ["database is locked", "no such table: system_settings"])
def test_settings_read_failure_returns_unavailable_instead_of_editable_defaults(db, monkeypatch, reason):
    db.add(SystemSetting(key="ai_model", value="stored-model"))
    db.commit()

    class UnavailableSettingsDB:
        def query(self, *args, **kwargs):
            raise OperationalError("synthetic settings query", {}, RuntimeError(reason))

    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: UnavailableSettingsDB())
    response = TestClient(app).get("/api/settings")

    assert response.status_code == 503
    assert response.json() == {"detail": "Settings unavailable; retry later"}
    db.expire_all()
    assert db.query(SystemSetting).filter(SystemSetting.key == "ai_model").one().value == "stored-model"


@pytest.mark.parametrize("invalid_threshold", [False, True])
def test_settings_resolves_all_providers_from_the_first_complete_snapshot(db, monkeypatch, invalid_threshold):
    for key, value in {
        "llm_model": "stored-model", "llm_base_url": "https://stored.example.test",
        "llm_thinking": "low", "pixelle_video_url": "http://stored-video:8500",
        "pixelle_video_timeout": "900", "decision_enabled": "false",
        "decision_min_confidence": "nan" if invalid_threshold else "0.6",
        "decision_min_probability": "0.85",
    }.items():
        db.add(SystemSetting(key=key, value=value))
    db.commit()

    class ReadOnceSettingsDB:
        queries = 0

        def query(self, *args, **kwargs):
            self.queries += 1
            if self.queries == 1:
                return db.query(*args, **kwargs)
            raise OperationalError("synthetic later query", {}, RuntimeError("database is locked"))

    snapshot_db = ReadOnceSettingsDB()
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: snapshot_db)
    response = TestClient(app).get("/api/settings")

    assert response.status_code == 200
    values = response.json()
    assert values["ai_model"] == "stored-model"
    assert values["ai_base_url"] == "https://stored.example.test"
    assert values["ai_thinking"] == "low"
    assert values["pixelle_video_url"] == "http://stored-video:8500"
    assert values["pixelle_video_timeout"] == "900"
    assert values["decision_enabled"] == "false"
    assert values["decision_min_probability"] == "0.85"
    if invalid_threshold:
        assert values["decision_min_confidence"] == "nan"
        assert values["decision_config_error"]
    else:
        assert values["decision_min_confidence"] == "0.6"
        assert "decision_config_error" not in values
    assert snapshot_db.queries == 1


def test_settings_write_rejects_a_failed_alias_read_without_partial_updates(db, monkeypatch):
    db.add(SystemSetting(key="llm_model", value="stored-model"))
    db.commit()

    class FailedAliasReadDB:
        queries = 0

        def query(self, *args, **kwargs):
            self.queries += 1
            if self.queries == 1:
                raise OperationalError("synthetic alias query", {}, RuntimeError("database is locked"))
            return db.query(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(db, name)

    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: FailedAliasReadDB())
    response = TestClient(app).put("/api/settings", json={"settings": {
        "ai_model": "replacement-model", "decision_enabled": "true",
    }})
    assert response.status_code == 503
    db.expire_all()
    assert db.query(SystemSetting).filter(SystemSetting.key == "llm_model").one().value == "stored-model"
    assert db.query(SystemSetting).filter(SystemSetting.key.in_(["ai_model", "decision_enabled"])).count() == 0
