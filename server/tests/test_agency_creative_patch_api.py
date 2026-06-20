from fastapi.testclient import TestClient

from app.db.models import AgencyCreativePatch, Episode, Series
from app.main import app

client = TestClient(app)


def _patch(db):
    series = Series(title="导演台 API", logline="一句话", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "原画面"}]},
    )
    db.add(episode)
    db.flush()
    patch = AgencyCreativePatch(
        series_id=series.id,
        episode_id=episode.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        patch_type="storyboard_patch",
        target_type="storyboard_frame",
        target_id="shot-001",
        title="强化钩子",
        reason="前三秒弱。",
        before_json={"image_prompt": "原"},
        after_json={"image_prompt": "新"},
        status="proposed",
        priority="high",
    )
    db.add(patch)
    db.commit()
    return series, episode, patch


def test_list_creative_patches_returns_summary_and_items(db):
    series, _, patch = _patch(db)

    response = client.get("/api/agency/creative-patches", params={"series_id": series.id})

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total"] == 1
    assert data["summary"]["blocking"] == 1
    assert data["items"][0]["id"] == patch.id
    assert data["items"][0]["after"] == {"image_prompt": "新"}


def test_update_approve_reject_and_apply_lifecycle(db):
    _, episode, patch = _patch(db)

    update = client.patch(f"/api/agency/creative-patches/{patch.id}", json={"after": {"image_prompt": "人工改后"}})
    assert update.status_code == 200
    assert update.json()["status"] == "edited"

    approve = client.post(f"/api/agency/creative-patches/{patch.id}/approve")
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    apply = client.post(f"/api/agency/creative-patches/{patch.id}/apply")
    assert apply.status_code == 200
    assert apply.json()["status"] == "applied"

    db.refresh(episode)
    assert episode.storyboard_json["frames"][0]["image_prompt"] == "人工改后"


def test_reject_patch_requires_reason(db):
    _, _, patch = _patch(db)

    response = client.post(f"/api/agency/creative-patches/{patch.id}/reject", json={})

    assert response.status_code == 422
    assert "原因" in response.json()["detail"]
