"""System settings API tests — masking sensitive values."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import SystemSetting
from app.database import get_db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()


def _clean_settings(db):
    db.query(SystemSetting).delete()
    db.commit()


def _set_setting(db, key, value):
    s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if s:
        s.value = value
    else:
        db.add(SystemSetting(key=key, value=value))
    db.commit()


def test_get_masks_sensitive_keys(client, db):
    """Sensitive keys (api_key) should return '****' in GET."""
    _clean_settings(db)
    _set_setting(db, "ai_api_key", "sk-secret-12345")
    _set_setting(db, "pixelle_api_key", "stage-secret")
    _set_setting(db, "ai_base_url", "https://api.deepseek.com")
    _set_setting(db, "ai_model", "deepseek-chat")

    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()

    # Sensitive fields masked
    assert data.get("ai_api_key") == "****"
    assert data.get("pixelle_api_key") == "****"
    # Non-sensitive fields returned as-is
    assert data.get("ai_base_url") == "https://api.deepseek.com"
    assert data.get("ai_model") == "deepseek-chat"


def test_put_skips_masked_value(client, db):
    """When value is '****', PUT should skip updating that key."""
    _clean_settings(db)
    _set_setting(db, "ai_api_key", "sk-original-key")

    # Send masked value — should NOT overwrite
    resp = client.put("/api/settings", json={
        "settings": {
            "ai_api_key": "****",
            "ai_base_url": "https://new.example.com",
        }
    })
    assert resp.status_code == 200

    # Verify: api_key unchanged, base_url updated
    actual = db.query(SystemSetting).filter(SystemSetting.key == "ai_api_key").first()
    assert actual.value == "sk-original-key"

    actual_url = db.query(SystemSetting).filter(SystemSetting.key == "ai_base_url").first()
    assert actual_url.value == "https://new.example.com"


def test_put_updates_new_value(client, db):
    """A non-masked value should update normally."""
    _clean_settings(db)
    _set_setting(db, "ai_api_key", "sk-old-key")

    resp = client.put("/api/settings", json={
        "settings": {"ai_api_key": "sk-new-key-xyz"}
    })
    assert resp.status_code == 200

    actual = db.query(SystemSetting).filter(SystemSetting.key == "ai_api_key").first()
    assert actual.value == "sk-new-key-xyz"


def test_put_creates_new_key(client, db):
    """PUT with a new key should create it."""
    resp = client.put("/api/settings", json={
        "settings": {"pixelle_video_url": "http://pixelle:8500"}
    })
    assert resp.status_code == 200

    actual = db.query(SystemSetting).filter(SystemSetting.key == "pixelle_video_url").first()
    assert actual is not None
    assert actual.value == "http://pixelle:8500"


def test_get_empty_settings(client, db):
    """When no settings exist, return empty dict."""
    _clean_settings(db)
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    assert resp.json() == {}
