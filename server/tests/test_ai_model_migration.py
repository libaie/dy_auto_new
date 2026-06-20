"""Migration idempotency and normalization tests."""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.migration import migrate_legacy_settings, _normalize_model_name, _find_existing


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_normalize_none_to_empty():
    assert _normalize_model_name(None) == ""


def test_normalize_whitespace():
    assert _normalize_model_name("  gpt-4  ") == "gpt-4"


def test_migration_idempotent(client, db):
    """Running migration twice should not create duplicates."""
    count_before = db.query(AIModel).count()
    result1 = migrate_legacy_settings(db)
    count_after_first = db.query(AIModel).count()
    result2 = migrate_legacy_settings(db)
    count_after_second = db.query(AIModel).count()
    assert count_after_first == count_after_second, \
        f"Migration not idempotent: {count_after_first} -> {count_after_second}"
    assert result2["created"] == 0, \
        f"Second run should create 0 models, created {result2['created']}"


def test_migration_handles_blank_model_name_dedup(client, db):
    """Duplicate (type, provider, '') should not be created by migration."""
    m = AIModel(
        id=str(uuid.uuid4()),
        name="Existing Pixelle", model_type="image", provider="pixelle",
        api_key=encrypt("key1"), model_name="",
    )
    db.add(m); db.commit()
    result = migrate_legacy_settings(db)
    pixelle_conflict = any(
        c.get("provider") == "pixelle" for c in result.get("conflicts", [])
    )
    pixelle_created = result.get("created", 0)
    assert pixelle_conflict or pixelle_created == 0, \
        "Should not create duplicate pixelle with blank model_name"


def test_migration_returns_result_structure(client, db):
    """Migration result must have created/skipped/conflicts keys."""
    result = migrate_legacy_settings(db)
    assert "created" in result
    assert "skipped" in result
    assert "conflicts" in result
    assert isinstance(result["conflicts"], list)


def test_seedance_env_migration_uses_ark_plan_v3(client, db, monkeypatch):
    import app.config as config

    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.setenv("SEEDANCE_API_KEY", "test-seedance-key")
    monkeypatch.setattr(config, "PIXELLE_VIDEO_URL", "http://localhost:8500")

    result = migrate_legacy_settings(db)

    assert result["created"] == 1
    model = db.query(AIModel).filter(
        AIModel.model_type == "video",
        AIModel.provider == "seedance",
    ).one()
    assert model.base_url == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert "/api/v3" not in model.base_url
    assert model.model_name == "doubao-seedance-2.0"
