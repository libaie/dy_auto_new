from fastapi.testclient import TestClient

from app.db_models import Episode, ProductionJob, ProductionPlan, Series, VideoProductionAsset, VideoProductionRun
from app.main import app
from app.services.production_status import JOB_BLOCKED
from app.services.video_production_run_types import REAL_SHORT_E2E


client = TestClient(app)


def _run(
    db,
    *,
    status="storyboard_ready",
    current_stage="storyboard_ready",
    run_type=REAL_SHORT_E2E,
    storyboard_frames=None,
):
    series = Series(title="Readiness", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status=status,
        current_stage=current_stage,
        run_type=run_type,
        storyboard_json={"frames": storyboard_frames or []},
    )
    db.add(run)
    db.commit()
    return run


def _asset(db, run, *, frame_id, asset_type, status, version=1):
    db.add(VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=frame_id,
        asset_type=asset_type,
        stage=asset_type,
        status=status,
        version=version,
    ))
    db.commit()


def test_readiness_exposes_run_type_and_next_action(db):
    run = _run(db)

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["run_id"] == run.id
    assert readiness["run_type"] == REAL_SHORT_E2E
    assert readiness["status"] == "storyboard_ready"
    assert readiness["current_stage"] == "storyboard_ready"
    assert readiness["next_action"]["key"] == "start_images"
    assert readiness["next_action"]["label"] == "开始生成图片"
    assert readiness["can_start_images"] is True
    assert readiness["can_complete_final"] is False


def test_readiness_blocks_video_until_images_approved(db):
    run = _run(
        db,
        status="image_review_pending",
        current_stage="image_review",
        storyboard_frames=[{"frame_id": "frame-001"}, {"frame_id": "frame-002"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="review_pending")
    _asset(db, run, frame_id="frame-002", asset_type="image", status="approved")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_start_videos"] is False
    assert readiness["can_complete_final"] is False
    assert readiness["needs_review"] is True
    assert readiness["next_action"]["key"] == "open_review"
    assert readiness["next_action"]["label"] == "打开审查"
    assert readiness["blocks"][0]["code"] == "IMAGE_REVIEW_REQUIRED"
    assert readiness["blocks"][0]["repair_route"] == f"/ai-video-review?run_id={run.id}"
    assert readiness["asset_counts"]["image"] == {
        "total": 2,
        "approved": 1,
        "pending": 1,
        "failed": 0,
    }


def test_readiness_missing_run_returns_named_error():
    resp = client.get("/api/video-production/runs/missing-run/readiness")

    assert resp.status_code == 404
    assert resp.json()["detail"] == {
        "code": "RUN_NOT_FOUND",
        "error_code": "RUN_NOT_FOUND",
        "message": "Video production run was not found.",
        "cause": "run_not_found",
        "repair_action": "Choose an existing production run.",
        "repair_route": "/video-production",
        "retryable": False,
        "affected_ids": ["missing-run"],
    }


def test_readiness_blocks_compose_when_video_segment_pending_on_other_status(db):
    run = _run(
        db,
        status="running",
        current_stage="video_rendering",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="approved")
    _asset(db, run, frame_id="frame-001", asset_type="video_segment", status="review_pending")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_compose"] is False
    assert readiness["can_complete_final"] is False
    assert readiness["needs_review"] is True
    assert readiness["next_action"]["key"] == "open_review"
    assert readiness["blocks"][0]["code"] == "VIDEO_REVIEW_REQUIRED"
    assert readiness["blocks"][0]["repair_route"] == f"/ai-video-review?run_id={run.id}"
    assert readiness["asset_counts"]["video_segment"]["pending"] == 1


def test_readiness_blocks_completion_when_final_video_pending_on_other_status(db):
    run = _run(db, status="running", current_stage="compose")
    _asset(db, run, frame_id="final", asset_type="final_video", status="review_pending")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_complete_final"] is False
    assert readiness["needs_review"] is True
    assert readiness["next_action"]["key"] == "open_review"
    assert readiness["blocks"][0]["code"] == "FINAL_REVIEW_REQUIRED"
    assert readiness["blocks"][0]["repair_route"] == f"/ai-video-review?run_id={run.id}"
    assert readiness["asset_counts"]["final_video"]["pending"] == 1


def test_readiness_blocks_completion_when_final_review_pending_has_pending_image(db):
    run = _run(
        db,
        status="final_review_pending",
        current_stage="final_review",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="review_pending")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_start_videos"] is False
    assert readiness["can_compose"] is False
    assert readiness["can_complete_final"] is False
    assert readiness["blocks"][0]["code"] == "IMAGE_REVIEW_REQUIRED"


def test_readiness_blocks_completion_when_final_review_pending_has_pending_video_segment(db):
    run = _run(
        db,
        status="final_review_pending",
        current_stage="final_review",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="approved")
    _asset(db, run, frame_id="frame-001", asset_type="video_segment", status="review_pending")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_compose"] is False
    assert readiness["can_complete_final"] is False
    assert readiness["blocks"][0]["code"] == "VIDEO_REVIEW_REQUIRED"


def test_readiness_blocks_completion_when_final_review_pending_has_pending_final_video(db):
    run = _run(db, status="final_review_pending", current_stage="final_review")
    _asset(db, run, frame_id="final", asset_type="final_video", status="review_pending")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_complete_final"] is False
    assert readiness["blocks"][0]["code"] == "FINAL_REVIEW_REQUIRED"


def test_readiness_counts_only_latest_asset_version_per_frame(db):
    run = _run(db, status="image_approved", current_stage="image_review")
    _asset(db, run, frame_id="frame-001", asset_type="image", status="review_pending", version=1)
    _asset(db, run, frame_id="frame-001", asset_type="image", status="rejected", version=2)
    _asset(db, run, frame_id="frame-001", asset_type="image", status="approved", version=3)

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_start_videos"] is True
    assert readiness["blocks"] == []
    assert readiness["asset_counts"]["image"] == {
        "total": 1,
        "approved": 1,
        "pending": 0,
        "failed": 0,
    }


def test_readiness_stage_gates_require_matching_run_status(db):
    run = _run(db, status="running", current_stage="video_rendering")
    _asset(db, run, frame_id="frame-001", asset_type="image", status="approved")
    _asset(db, run, frame_id="frame-001", asset_type="video_segment", status="approved")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_start_videos"] is False
    assert readiness["can_compose"] is False


def test_readiness_blocks_start_videos_when_expected_image_is_missing(db):
    run = _run(
        db,
        status="image_approved",
        current_stage="image_review",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_start_videos"] is False
    assert readiness["blocks"][0]["code"] == "IMAGE_REVIEW_REQUIRED"


def test_readiness_blocks_compose_when_expected_video_segment_is_missing(db):
    run = _run(
        db,
        status="video_segments_approved",
        current_stage="video_review",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="approved")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_compose"] is False
    assert readiness["blocks"][0]["code"] == "VIDEO_REVIEW_REQUIRED"


def test_readiness_blocks_start_videos_when_latest_image_is_regenerating(db):
    run = _run(
        db,
        status="image_approved",
        current_stage="image_review",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="regenerating")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_start_videos"] is False
    assert readiness["blocks"][0]["code"] == "IMAGE_REVIEW_REQUIRED"
    assert readiness["asset_counts"]["image"] == {
        "total": 1,
        "approved": 0,
        "pending": 1,
        "failed": 0,
    }


def test_readiness_blocks_compose_when_latest_video_segment_is_regenerating(db):
    run = _run(
        db,
        status="video_segments_approved",
        current_stage="video_review",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="approved")
    _asset(db, run, frame_id="frame-001", asset_type="video_segment", status="regenerating")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_compose"] is False
    assert readiness["blocks"][0]["code"] == "VIDEO_REVIEW_REQUIRED"
    assert readiness["asset_counts"]["video_segment"] == {
        "total": 1,
        "approved": 0,
        "pending": 1,
        "failed": 0,
    }


def test_readiness_ignores_non_expected_image_for_start_video_gate(db):
    run = _run(
        db,
        status="image_approved",
        current_stage="image_review",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="approved")
    _asset(db, run, frame_id="obsolete-frame", asset_type="image", status="review_pending")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_start_videos"] is True
    assert readiness["blocks"] == []
    assert readiness["asset_counts"]["image"] == {
        "total": 2,
        "approved": 1,
        "pending": 1,
        "failed": 0,
    }


def test_readiness_ignores_non_expected_video_for_compose_gate(db):
    run = _run(
        db,
        status="video_segments_approved",
        current_stage="video_review",
        storyboard_frames=[{"frame_id": "frame-001"}],
    )
    _asset(db, run, frame_id="frame-001", asset_type="image", status="approved")
    _asset(db, run, frame_id="frame-001", asset_type="video_segment", status="approved")
    _asset(db, run, frame_id="obsolete-frame", asset_type="video_segment", status="rejected")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_compose"] is True
    assert readiness["blocks"] == []
    assert readiness["asset_counts"]["video_segment"] == {
        "total": 2,
        "approved": 1,
        "pending": 0,
        "failed": 1,
    }


def test_readiness_can_complete_final_for_final_review_pending(db):
    run = _run(db, status="final_review_pending", current_stage="final_review")

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_complete_final"] is True


def test_readiness_blocks_final_review_when_compose_job_blocked_without_final_asset(db):
    run = _run(db, status="final_review_pending", current_stage="final_review")
    plan = ProductionPlan(series_id=run.series_id, status="running")
    db.add(plan)
    db.flush()
    run.production_plan_id = plan.id
    job = ProductionJob(
        plan_id=plan.id,
        stage="episode_compose",
        status=JOB_BLOCKED,
        target_type="episode",
        target_id=run.episode_id,
        error_code="COMPOSE_PREFLIGHT_BLOCKED",
        error_message="Compose preflight needs repair.",
        idempotency_key=f"{run.id}:episode_compose",
    )
    db.add(job)
    db.commit()

    resp = client.get(f"/api/video-production/runs/{run.id}/readiness")

    assert resp.status_code == 200
    readiness = resp.json()["readiness"]
    assert readiness["can_complete_final"] is False
    assert readiness["needs_review"] is True
    assert readiness["next_action"]["key"] == "repair_provider_stage"
    assert readiness["blocks"][0]["code"] == "COMPOSE_PREFLIGHT_BLOCKED"
    assert readiness["blocks"][0]["repair_route"] == f"/video-production/{run.id}"
