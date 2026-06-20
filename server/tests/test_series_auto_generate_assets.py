from fastapi.testclient import TestClient

from app.db_models import Series
from app.main import app


client = TestClient(app)


def test_auto_generate_assets_uses_long_model_timeout(db, monkeypatch):
    from app.routers import series as series_router

    series = Series(
        title="City Healer",
        logline="A young doctor solves urban mysteries with a consistent cyber-noir style.",
        genre="drama",
    )
    db.add(series)
    db.commit()

    calls = []

    async def fake_generate_custom(_db, _system_prompt, _user_prompt, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return """
            {
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
            """
        return """
        {
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
        """

    monkeypatch.setattr(series_router.ai_generator, "generate_custom", fake_generate_custom)

    resp = client.post(f"/api/series/{series.id}/auto-generate")

    assert resp.status_code == 200
    assert [call["request_timeout_seconds"] for call in calls] == [
        series_router.AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS,
        series_router.AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS,
    ]
