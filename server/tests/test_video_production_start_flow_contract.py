from fastapi.testclient import TestClient

from app.db_models import ProductionAuditEvent, ProductionJob, ProductionPlan, ProductionSegment, VideoProductionRun, Series, Episode
from app.main import app
from app.services.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E


def _series_episode(db, *, locked=True, storyboard=True):
    series = Series(
        title="Start Flow",
        logline="One sentence",
        genre="drama",
        target_duration=10,
        story_bible_json={
            "style_lock": {
                "locked": locked,
                "version": 1,
                "visual_style": {"prompt": "realistic documentary"},
                "characters": [{
                    "id": "char-1",
                    "name": "老李",
                    "reference_urls": ["/static/characters/laoli-front.png"],
                }],
                "scenes": [{
                    "id": "scene-1",
                    "name": "社区公园",
                    "reference_urls": ["/static/scenes/park.png"],
                }],
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={
            "frames": [{
                "frame_id": "shot-1",
                "scene_id": "scene-1",
                "duration": 10,
                "image_prompt": "A",
                "video_prompt": "B",
                "reference_urls": ["/static/characters/laoli-front.png", "/static/scenes/park.png"],
            }]
        } if storyboard else {"frames": []},
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_start_flow_auto_generates_missing_storyboard_before_creating_run(db, monkeypatch):
    series, episode = _series_episode(db, storyboard=False)
    client = TestClient(app)

    async def fake_generate_custom(*args, **kwargs):
        return """
        {"frames":[{"frame_id":"shot-1","scene_id":"scene-1","character_ids":["char-1"],"duration":10,
        "image_prompt":"老李在社区公园讲控糖经验","narration":"控糖第一步，先看早餐。","audio_mode":"tts",
        "continuity_notes":"保持真实纪录片质感。"}]}
        """

    monkeypatch.setattr("app.services.ai_generator.ai_generator.generate_custom", fake_generate_custom)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    db.refresh(episode)
    assert episode.storyboard_json["frames"][0]["reference_urls"]
    assert resp.json()["run"]["production_link_status"] == "linked"
    assert db.query(ProductionSegment).count() == 2


def test_start_flow_creates_plan_segments_linked_run_and_returns_route(db):
    series, episode = _series_episode(db)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["route"] == f"/video-production/{body['run']['id']}"
    assert body["run"]["production_link_status"] == "linked"
    assert db.query(ProductionSegment).count() == 2

    run = db.query(VideoProductionRun).filter_by(id=body["run"]["id"]).one()
    assert run.production_plan_id
    assert run.production_episode_id
    assert run.model_trace_json["autopilot"] == {"enabled": False, "source": "episode_start"}
    assert db.query(ProductionAuditEvent).filter_by(run_id=run.id, event_type="run.created").count() == 1
    db.refresh(episode)
    assert episode.status == "rendering"


def test_start_flow_preserves_real_short_run_type_from_request(db):
    series, episode = _series_episode(db)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
        "run_type": REAL_SHORT_E2E,
    })

    assert resp.status_code == 200
    run = db.query(VideoProductionRun).filter_by(id=resp.json()["run"]["id"]).one()
    plan = db.query(ProductionPlan).filter_by(id=run.production_plan_id).one()
    assert run.run_type == REAL_SHORT_E2E
    assert plan.budget_limit == 1


def test_real_short_start_flow_autostart_images_enqueues_without_synchronous_agency_review(db, monkeypatch):
    series, episode = _series_episode(db)
    client = TestClient(app)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("start flow must not synchronously run agency review")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", fail_if_called)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "budget_limit": 1,
        "run_type": REAL_SHORT_E2E,
    })

    assert resp.status_code == 200
    run = db.query(VideoProductionRun).filter_by(id=resp.json()["run"]["id"]).one()
    assert run.status == "image_batch_running"
    assert run.model_trace_json["autopilot"] == {"enabled": True, "source": "episode_start"}
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="image_generation").count() == 2


def test_start_flow_creates_isolated_plan_and_jobs_for_each_run(db):
    series, episode = _series_episode(db)
    client = TestClient(app)

    first = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "budget_limit": 1,
        "run_type": REAL_SHORT_E2E,
    })
    second = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "budget_limit": 1,
        "run_type": REAL_SHORT_E2E,
    })

    assert first.status_code == 200
    assert second.status_code == 200
    first_plan_id = first.json()["run"]["production_plan_id"]
    second_plan_id = second.json()["run"]["production_plan_id"]
    assert first_plan_id != second_plan_id
    assert db.query(ProductionJob).filter_by(plan_id=first_plan_id, stage="image_generation").count() == 2
    assert db.query(ProductionJob).filter_by(plan_id=second_plan_id, stage="image_generation").count() == 2


def test_start_flow_rejects_mock_series_scale_before_linked_plan_mutation(db):
    series, episode = _series_episode(db)
    client = TestClient(app)

    before = {
        "runs": db.query(VideoProductionRun).count(),
        "plans": db.query(ProductionPlan).count(),
    }
    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 240 * 60,
        "autostart_images": False,
        "run_type": MOCK_SERIES_SCALE,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "INVALID_RUN_TYPE"
    assert {
        "runs": db.query(VideoProductionRun).count(),
        "plans": db.query(ProductionPlan).count(),
    } == before


def test_start_flow_returns_repairable_error_when_style_is_unlocked(db):
    series, episode = _series_episode(db, locked=False)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "STYLE_LOCK_MISSING"
