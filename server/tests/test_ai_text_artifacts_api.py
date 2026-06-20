from fastapi.testclient import TestClient

from app.db_models import Episode, Series
from app.main import app


client = TestClient(app)


def _create_series_episode(db):
    series = Series(title="Transparent Series", total_episodes=3, status="draft")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="planned")
    db.add(episode)
    db.commit()
    return series, episode


def test_ai_text_artifacts_api_lists_and_edits_versions(db):
    from app.services.ai_text_artifact_service import AITextArtifactService

    series, episode = _create_series_episode(db)
    artifact = AITextArtifactService(db).create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
        source_type="ai",
        input_json={"prompt": "draft script"},
        content_text="AI script",
        model_trace_json={"provider": "test"},
    )

    list_resp = client.get(f"/api/ai-text-artifacts?series_id={series.id}&artifact_type=episode_script")
    assert list_resp.status_code == 200
    listed = list_resp.json()["artifacts"]
    assert listed[0]["id"] == artifact.id
    assert listed[0]["content_text"] == "AI script"
    assert listed[0]["model_trace_json"] == {"provider": "test"}

    detail_resp = client.get(f"/api/ai-text-artifacts/{artifact.id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["artifact"]["input_json"] == {"prompt": "draft script"}

    edit_resp = client.post(f"/api/ai-text-artifacts/{artifact.id}/edit", json={
        "content_text": "Human edited script",
        "content_json": {"scenes": [{"summary": "edited"}]},
    })
    assert edit_resp.status_code == 200
    edited = edit_resp.json()["artifact"]
    assert edited["version"] == 2
    assert edited["source_type"] == "human_edit"
    assert edited["parent_artifact_id"] == artifact.id

    approve_resp = client.post(f"/api/ai-text-artifacts/{edited['id']}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["artifact"]["status"] == "approved"

    lineage_resp = client.get(f"/api/ai-text-artifacts/{edited['id']}/lineage")
    assert lineage_resp.status_code == 200
    assert [item["version"] for item in lineage_resp.json()["artifacts"]] == [1, 2]


def test_ai_text_artifact_read_routes_require_auth(real_auth):
    list_resp = client.get("/api/ai-text-artifacts")
    detail_resp = client.get("/api/ai-text-artifacts/artifact-1")
    lineage_resp = client.get("/api/ai-text-artifacts/artifact-1/lineage")

    assert list_resp.status_code == 401
    assert detail_resp.status_code == 401
    assert lineage_resp.status_code == 401


def test_ai_text_artifact_write_routes_require_admin_role(db, real_auth):
    from app.deps import create_access_token
    from app.services.ai_text_artifact_service import AITextArtifactService

    series, episode = _create_series_episode(db)
    artifact = AITextArtifactService(db).create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
        source_type="ai",
        content_text="AI script",
    )
    token = create_access_token("operator-id", "operator", "operator")
    headers = {"Authorization": f"Bearer {token}"}

    edit_resp = client.post(
        f"/api/ai-text-artifacts/{artifact.id}/edit",
        headers=headers,
        json={"content_text": "operator edit"},
    )
    approve_resp = client.post(f"/api/ai-text-artifacts/{artifact.id}/approve", headers=headers)
    regenerate_resp = client.post(
        f"/api/ai-text-artifacts/{artifact.id}/regenerate",
        headers=headers,
        json={"input_json": {"instruction": "retry"}},
    )

    assert edit_resp.status_code == 403
    assert approve_resp.status_code == 403
    assert regenerate_resp.status_code == 403


def test_ai_text_artifact_api_rejects_approving_stale_version(db):
    from app.services.ai_text_artifact_service import AITextArtifactService

    series, episode = _create_series_episode(db)
    service = AITextArtifactService(db)
    artifact = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
        source_type="ai",
        content_text="AI script v1",
    )
    edited = service.edit_artifact(
        artifact.id,
        content_text="Human edited script v2",
        content_json={"scenes": [{"summary": "edited"}]},
    )

    resp = client.post(f"/api/ai-text-artifacts/{artifact.id}/approve")

    assert resp.status_code == 409
    db.refresh(edited)
    assert edited.status == "review_pending"


def test_ai_text_artifacts_api_regenerate_calls_ai_and_creates_reviewable_child_version(db, monkeypatch):
    from app.services.ai_text_artifact_service import AITextArtifactService

    series, episode = _create_series_episode(db)
    artifact = AITextArtifactService(db).create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="storyboard",
        source_type="ai",
        input_json={"prompt": "original storyboard"},
        content_json={"frames": [{"narration": "old hook"}]},
        content_text="old hook",
    )
    seen = {}

    async def fake_generate_custom(db_session, system_prompt, user_prompt, **kwargs):
        seen["system_prompt"] = system_prompt
        seen["user_prompt"] = user_prompt
        seen["kwargs"] = kwargs
        return '{"frames":[{"narration":"new AI hook"}]}'

    monkeypatch.setattr("app.services.ai_generator.ai_generator.generate_custom", fake_generate_custom)

    resp = client.post(f"/api/ai-text-artifacts/{artifact.id}/regenerate", json={
        "input_json": {"instruction": "make the hook clearer"},
    })

    assert resp.status_code == 200
    regenerated = resp.json()["artifact"]
    assert regenerated["version"] == 2
    assert regenerated["source_type"] == "ai_regenerate"
    assert regenerated["parent_artifact_id"] == artifact.id
    assert regenerated["status"] == "review_pending"
    assert regenerated["input_json"]["instruction"] == "make the hook clearer"
    assert regenerated["input_json"]["parent_artifact_id"] == artifact.id
    assert regenerated["content_json"] == {"frames": [{"narration": "new AI hook"}]}
    assert regenerated["content_text"] == '{"frames":[{"narration":"new AI hook"}]}'
    assert regenerated["model_trace_json"]["source"] == "ai_regenerate"
    assert regenerated["model_trace_json"]["raw_output"] == '{"frames":[{"narration":"new AI hook"}]}'
    assert "old hook" in seen["user_prompt"]
    assert "make the hook clearer" in seen["user_prompt"]
