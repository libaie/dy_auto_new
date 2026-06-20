from fastapi.testclient import TestClient

from app.db.models import Character, Scene
from app.main import app


def test_archived_characters_hidden_by_default_and_visible_when_requested(db):
    active = Character(name="Active")
    archived = Character(name="Archived", meta_json={"archived": True, "archived_at": "2026-06-01T00:00:00"})
    db.add_all([active, archived])
    db.commit()
    client = TestClient(app)

    default_resp = client.get("/api/characters")
    assert default_resp.status_code == 200
    assert [c["name"] for c in default_resp.json()["characters"]] == ["Active"]

    archived_resp = client.get("/api/characters?include_archived=true")
    assert archived_resp.status_code == 200
    assert {c["name"] for c in archived_resp.json()["characters"]} == {"Active", "Archived"}


def test_archived_scenes_hidden_by_default_and_visible_when_requested(db):
    active = Scene(name="Active")
    archived = Scene(name="Archived", meta_json={"archived": True, "archived_at": "2026-06-01T00:00:00"})
    db.add_all([active, archived])
    db.commit()
    client = TestClient(app)

    default_resp = client.get("/api/scenes")
    assert default_resp.status_code == 200
    assert [s["name"] for s in default_resp.json()["scenes"]] == ["Active"]

    archived_resp = client.get("/api/scenes?include_archived=true")
    assert archived_resp.status_code == 200
    assert {s["name"] for s in archived_resp.json()["scenes"]} == {"Active", "Archived"}
