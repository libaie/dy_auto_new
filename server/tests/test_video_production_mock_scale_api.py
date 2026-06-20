from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db.models import Episode, ProductionJob, ProductionSegment, Series, VideoProductionAsset, VideoProductionRun
from app.main import app
from app.domains.video_production.production_status import JOB_COMPLETED, JOB_QUEUED
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE
from app.domains.video_production.video_production_service import start_compose_stage, start_image_stage, start_video_stage


client = TestClient(app)


def _one_sentence_payload(**overrides):
    payload = {
        "prompt": "A courier delivers a message across a neon city.",
        "title": "Courier",
        "genre": "sci-fi",
        "target_duration_seconds": 60,
        "autostart_images": False,
        "run_type": MOCK_SERIES_SCALE,
    }
    payload.update(overrides)
    return payload


def _asset(db, run, frame_id, asset_type, status="review_pending"):
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=frame_id,
        asset_type=asset_type,
        stage="composition" if asset_type == "final_video" else f"{asset_type}_stage",
        url=f"https://cdn.test/{run.id}/{frame_id}/{asset_type}",
        version=1,
        status=status,
    )
    db.add(asset)
    db.commit()
    return asset


def _mock_run_ref():
    return SimpleNamespace(**client.post("/api/video-production/one-sentence", json=_one_sentence_payload()).json()["run"])


def test_one_sentence_mock_scale_creates_run_and_worker_step_advances_queue(db):
    create_resp = client.post(
        "/api/video-production/one-sentence",
        json=_one_sentence_payload(target_duration_seconds=480 * 60),
    )

    assert create_resp.status_code == 200
    body = create_resp.json()
    run = body["run"]
    assert run["run_type"] == MOCK_SERIES_SCALE
    assert run["status"] == "mock_scheduler_pending"
    assert run["model_trace_json"]["job_count"] == 480

    queued_before = db.query(ProductionJob).filter_by(
        plan_id=run["production_plan_id"],
        status=JOB_QUEUED,
    ).count()
    assert queued_before == 480

    step_resp = client.post(
        f"/api/video-production/runs/{run['id']}/mock-worker-step",
        json={"lease_id": "test-worker", "batch_size": 3},
    )

    assert step_resp.status_code == 200
    step_body = step_resp.json()
    assert step_body["ok"] is True
    assert step_body["lease_id"] == "test-worker"
    assert step_body["processed"] == 3
    assert step_body["remaining"] == 477
    assert step_body["run"]["status"] == "mock_scheduler_running"
    assert db.query(ProductionJob).filter_by(
        plan_id=run["production_plan_id"],
        status=JOB_COMPLETED,
    ).count() == 3


def test_mock_worker_step_returns_structured_errors_for_missing_or_non_mock_run(db):
    missing = client.post("/api/video-production/runs/missing-run/mock-worker-step", json={})
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "RUN_NOT_FOUND"

    series = Series(title="Real", logline="Real", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", storyboard_json={"frames": []})
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, run_type="real_short_e2e")
    db.add(run)
    db.commit()

    invalid = client.post(f"/api/video-production/runs/{run.id}/mock-worker-step", json={})
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "INVALID_RUN_TYPE"


@pytest.mark.asyncio
@pytest.mark.parametrize("starter", [start_image_stage, start_video_stage, start_compose_stage])
async def test_mock_series_scale_cannot_enter_real_provider_stages(db, monkeypatch, starter):
    create_resp = client.post("/api/video-production/one-sentence", json=_one_sentence_payload())
    run_id = create_resp.json()["run"]["id"]

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("mock_series_scale entered provider stage")

    monkeypatch.setattr("app.domains.video_production.video_production_service._guard_provider_stage", fail_if_called)

    with pytest.raises(Exception) as exc_info:
        await starter(db, run_id)

    assert MOCK_SERIES_SCALE in str(exc_info.value)


@pytest.mark.parametrize("asset_type", ["image", "video_segment"])
def test_mock_series_scale_cannot_start_asset_regeneration_provider_path(db, monkeypatch, asset_type):
    run = _mock_run_ref()
    segment = db.query(ProductionSegment).first()
    frame_id = segment.id
    production_segment_id = segment.id
    if asset_type == "video_segment":
        approved_image = _asset(db, run, frame_id, "image", status="approved")
        approved_image.production_segment_id = production_segment_id
        approved_image.is_latest = True
        db.commit()

    asset = _asset(db, run, frame_id, asset_type, status="rejected")
    asset.production_segment_id = production_segment_id
    asset.is_latest = True
    db.commit()

    monkeypatch.setattr(
        "app.domains.video_production.video_production_service.resolve_runtime_model_config",
        lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": scene},
    )

    async def fail_submit(*args, **kwargs):
        raise AssertionError("mock_series_scale entered provider submit")

    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fail_submit)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_video_batch", fail_submit)

    resp = client.post(f"/api/video-production/assets/{asset.id}/start-regeneration")

    assert resp.status_code == 400
    assert MOCK_SERIES_SCALE in resp.json()["detail"]


def test_review_items_returns_gate_counts_for_current_run_only(db):
    first = client.post("/api/video-production/one-sentence", json=_one_sentence_payload()).json()["run"]
    second = client.post("/api/video-production/one-sentence", json=_one_sentence_payload(title="Other")).json()["run"]
    first_run = SimpleNamespace(**first)
    second_run = SimpleNamespace(**second)
    for asset_type in ("image", "video_segment", "final_video"):
        _asset(db, first_run, f"{asset_type}-1", asset_type)
        _asset(db, second_run, f"{asset_type}-other", asset_type)
        _asset(db, first_run, f"{asset_type}-failed", asset_type, status="failed")
        _asset(db, first_run, f"{asset_type}-rejected", asset_type, status="rejected")
        _asset(db, first_run, f"{asset_type}-regenerating", asset_type, status="regenerating")
    _asset(db, first_run, "approved-image", "image", status="approved")

    resp = client.get(f"/api/video-production/review-items?run_id={first['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["gate_counts"] == {"image": 1, "video_segment": 1, "final_video": 1}
    assert body["total"] == 12
