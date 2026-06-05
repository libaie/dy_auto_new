import pytest
from fastapi.testclient import TestClient

from app.db_models import Character, Scene
from app.main import app


@pytest.mark.asyncio
async def test_character_rewrite_returns_candidate_without_mutating_row(db, monkeypatch):
    from app.services import asset_ai_rewrite_service

    character = Character(
        name="Lin",
        role_type="protagonist",
        gender="female",
        age_range="28-32",
        personality="calm and precise",
        appearance_desc="short black hair and sharp eyes",
        outfit_desc="long gray coat",
        default_voice_id="voice-a",
    )
    db.add(character)
    db.commit()
    original_id = character.id

    async def fake_generate_custom(db_session, system_prompt, user_prompt, **kwargs):
        assert "candidate" in system_prompt
        assert "make her warmer" in user_prompt
        return """```json
{"candidate":{"name":"Lin Wei","personality":"warm but precise","appearance_desc":"soft eyes","ignored":"drop me"}}
```"""

    monkeypatch.setattr(asset_ai_rewrite_service.ai_generator, "generate_custom", fake_generate_custom)

    result = await asset_ai_rewrite_service.generate_character_rewrite_candidate(
        db, original_id, instruction="make her warmer"
    )

    assert result["ok"] is True
    assert result["asset_type"] == "character"
    assert result["asset_id"] == original_id
    assert result["current"]["name"] == "Lin"
    assert result["candidate"] == {
        "name": "Lin Wei",
        "personality": "warm but precise",
        "appearance_desc": "soft eyes",
    }
    assert result["warnings"] == []
    assert result["missing_requirements"] == []

    db.refresh(character)
    assert character.name == "Lin"
    assert character.personality == "calm and precise"
    assert character.appearance_desc == "short black hair and sharp eyes"


@pytest.mark.asyncio
async def test_scene_rewrite_returns_candidate_without_mutating_row(db, monkeypatch):
    from app.services import asset_ai_rewrite_service

    scene = Scene(
        name="Rain Clinic",
        scene_type="indoor",
        location_desc="small clinic with neon reflections",
        lighting="night",
        mood="mysterious",
    )
    db.add(scene)
    db.commit()
    original_id = scene.id

    async def fake_generate_custom(db_session, system_prompt, user_prompt, **kwargs):
        assert "scene_type" in system_prompt
        return 'notes before {"name":"Rain Clinic Lobby","lighting":"warm_indoor","mood":"tense","extra":"drop"} notes after'

    monkeypatch.setattr(asset_ai_rewrite_service.ai_generator, "generate_custom", fake_generate_custom)

    result = await asset_ai_rewrite_service.generate_scene_rewrite_candidate(db, original_id)

    assert result["ok"] is True
    assert result["asset_type"] == "scene"
    assert result["asset_id"] == original_id
    assert result["current"]["name"] == "Rain Clinic"
    assert result["candidate"] == {
        "name": "Rain Clinic Lobby",
        "lighting": "warm_indoor",
        "mood": "tense",
    }

    db.refresh(scene)
    assert scene.name == "Rain Clinic"
    assert scene.lighting == "night"
    assert scene.mood == "mysterious"


@pytest.mark.asyncio
async def test_invalid_ai_json_raises_ai_rewrite_invalid_output(db, monkeypatch):
    from app.services import asset_ai_rewrite_service

    character = Character(name="Lin")
    db.add(character)
    db.commit()

    async def fake_generate_custom(db_session, system_prompt, user_prompt, **kwargs):
        return "not json"

    monkeypatch.setattr(asset_ai_rewrite_service.ai_generator, "generate_custom", fake_generate_custom)

    with pytest.raises(asset_ai_rewrite_service.AssetAiRewriteError) as exc_info:
        await asset_ai_rewrite_service.generate_character_rewrite_candidate(db, character.id)

    assert exc_info.value.code == "AI_REWRITE_INVALID_OUTPUT"
    assert "raw_preview" in exc_info.value.details


@pytest.mark.asyncio
async def test_not_found_raises_correct_code(db):
    from app.services.asset_ai_rewrite_service import (
        AssetAiRewriteError,
        generate_character_rewrite_candidate,
        generate_scene_rewrite_candidate,
    )

    with pytest.raises(AssetAiRewriteError) as character_exc:
        await generate_character_rewrite_candidate(db, "missing-character")
    assert character_exc.value.code == "CHARACTER_NOT_FOUND"

    with pytest.raises(AssetAiRewriteError) as scene_exc:
        await generate_scene_rewrite_candidate(db, "missing-scene")
    assert scene_exc.value.code == "SCENE_NOT_FOUND"


def test_character_ai_rewrite_candidate_endpoint_returns_candidate(db, monkeypatch):
    from app.services import asset_ai_rewrite_service

    character = Character(name="Lin", role_type="protagonist", gender="female")
    db.add(character)
    db.commit()

    async def fake_generate_custom(db_session, system_prompt, user_prompt, **kwargs):
        return '{"candidate":{"name":"Lin Wei","personality":"warm"}}'

    monkeypatch.setattr(asset_ai_rewrite_service.ai_generator, "generate_custom", fake_generate_custom)

    client = TestClient(app)
    response = client.post(
        f"/api/characters/{character.id}/ai-rewrite-candidate",
        json={"instruction": "warm up"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["asset_type"] == "character"
    assert body["asset_id"] == character.id
    assert body["candidate"] == {"name": "Lin Wei", "personality": "warm"}


def test_scene_ai_rewrite_candidate_endpoint_returns_candidate(db, monkeypatch):
    from app.services import asset_ai_rewrite_service

    scene = Scene(name="Clinic", scene_type="indoor", lighting="night")
    db.add(scene)
    db.commit()

    async def fake_generate_custom(db_session, system_prompt, user_prompt, **kwargs):
        return '{"candidate":{"name":"Clinic Lobby","mood":"tense"}}'

    monkeypatch.setattr(asset_ai_rewrite_service.ai_generator, "generate_custom", fake_generate_custom)

    client = TestClient(app)
    response = client.post(f"/api/scenes/{scene.id}/ai-rewrite-candidate", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["asset_type"] == "scene"
    assert body["asset_id"] == scene.id
    assert body["candidate"] == {"name": "Clinic Lobby", "mood": "tense"}


def test_character_ai_rewrite_candidate_endpoint_maps_not_found_to_structured_404():
    client = TestClient(app)

    response = client.post("/api/characters/missing-character/ai-rewrite-candidate", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "CHARACTER_NOT_FOUND",
        "message": "Character not found",
        "details": {"character_id": "missing-character"},
    }
