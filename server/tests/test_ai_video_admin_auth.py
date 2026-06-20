from fastapi.testclient import TestClient

from app.deps import create_access_token
from app.main import app


client = TestClient(app)


def _auth_headers(role: str) -> dict:
    token = create_access_token(f"{role}-user-id", f"{role}-user", role)
    return {"Authorization": f"Bearer {token}"}


def test_non_admin_cannot_start_one_sentence_production(real_auth, monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("non-admin request reached one-sentence production")

    monkeypatch.setattr("app.domains.video_production.video_production_router.create_one_sentence_video", fail_if_called)

    response = client.post(
        "/api/video-production/one-sentence",
        headers=_auth_headers("operator"),
        json={
            "prompt": "A short video prompt with enough detail.",
            "target_duration_seconds": 60,
            "budget_limit": 1,
            "autostart_images": False,
        },
    )

    assert response.status_code == 403


def test_non_admin_cannot_start_episode_production(real_auth, monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("non-admin request reached episode production")

    monkeypatch.setattr("app.domains.video_production.production_run_service.start_episode_production", fail_if_called)

    response = client.post(
        "/api/video-production/runs/start",
        headers=_auth_headers("operator"),
        json={
            "series_id": "series-1",
            "episode_id": "episode-1",
            "target_duration_seconds": 60,
            "budget_limit": 1,
            "autostart_images": False,
            "run_type": "real_short_e2e",
        },
    )

    assert response.status_code == 403
