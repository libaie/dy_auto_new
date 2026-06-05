from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.video_production_run_types import REAL_SHORT_E2E
from app.services.video_production_service import run_ai_audit_for_assets


def test_ai_audit_pass_does_not_human_approve_image_gate(db, monkeypatch):
    series = Series(title="Audit Gate", logline="Audit", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "duration": 5}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=REAL_SHORT_E2E,
        status="image_batch_running",
        current_stage="image_generation",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/frame-001.png",
        version=1,
        status="review_pending",
    )
    db.add(asset)
    db.commit()

    monkeypatch.setattr(
        "app.services.video_production_service.resolve_runtime_model_config",
        lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"},
    )
    monkeypatch.setattr(
        "app.routers.audit._do_audit",
        lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []},
    )

    run_ai_audit_for_assets(db, run, [asset])

    db.refresh(asset)
    db.refresh(run)
    ai_review = db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="ai").one()
    assert ai_review.status == "approved"
    assert asset.status == "review_pending"
    assert run.status == "image_review_pending"


def test_autopilot_run_auto_approves_image_when_audit_model_is_unavailable(db, monkeypatch):
    series = Series(title="Autopilot Audit Gate", logline="Audit", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "duration": 5}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=REAL_SHORT_E2E,
        status="image_batch_running",
        current_stage="image_generation",
        storyboard_json=episode.storyboard_json,
        model_trace_json={"autopilot": {"enabled": True, "source": "test"}},
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/frame-001.png",
        local_path="output/frame-001.png",
        storage_path="output/frame-001.png",
        checksum="frame-001",
        copy_status="persisted",
        version=1,
        status="review_pending",
        is_latest=True,
    )
    db.add(asset)
    db.commit()

    monkeypatch.setattr(
        "app.services.video_production_service.resolve_runtime_model_config",
        lambda db, scene: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )

    run_ai_audit_for_assets(db, run, [asset])

    db.refresh(asset)
    db.refresh(run)
    auto_review = db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="auto").one()
    ai_review = db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="ai").one()
    assert ai_review.status == "needs_human"
    assert auto_review.status == "approved"
    assert auto_review.model_trace_json["auto_review_policy"]["source"] == "autopilot"
    assert asset.status == "approved"
    assert run.status == "image_approved"
