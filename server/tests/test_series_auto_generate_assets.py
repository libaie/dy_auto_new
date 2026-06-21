from fastapi.testclient import TestClient

from app.db.models import Series
from app.main import app


client = TestClient(app)


def test_auto_generate_assets_uses_structured_langchain_runtime_config(db, monkeypatch):
    from app.domains.ai_video_series import style_lock
    series = Series(
        title="City Healer",
        logline="A young doctor solves urban mysteries with a consistent cyber-noir style.",
        genre="drama",
    )
    db.add(series)
    db.commit()

    resolved_scene_keys = []
    calls = []

    def fake_resolve_runtime_model_config(_db, scene_key):
        resolved_scene_keys.append(scene_key)
        return {"scene_key": scene_key, "provider": "test", "model": "script-model"}

    async def fake_run_structured_ai_video_json(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
              "characters": [
                {
                  "name": "Lin",
                  "role_type": "protagonist",
                  "gender": "female",
                  "age_range": "25-30",
                  "personality": "Focused and kind.",
                  "appearance_desc": "Short black hair and sharp eyes.",
                  "outfit_desc": "Gray coat."
                }
              ]
            }
        return {
          "scenes": [
            {
              "name": "Rain Clinic",
              "scene_type": "indoor",
              "location_desc": "Small clinic with neon reflections.",
              "lighting": "night",
              "mood": "mysterious"
            }
          ]
        }

    monkeypatch.setattr(style_lock, "resolve_runtime_model_config", fake_resolve_runtime_model_config)
    monkeypatch.setattr(style_lock, "run_structured_ai_video_json", fake_run_structured_ai_video_json)

    resp = client.post(f"/api/series/{series.id}/auto-generate")

    assert resp.status_code == 200
    assert resolved_scene_keys == ["script_generation", "script_generation"]
    assert [call["runtime_config"]["scene_key"] for call in calls] == ["script_generation", "script_generation"]
    assert all(call["allowed_tools"] == ["validate_json", "read_series_context"] for call in calls)
