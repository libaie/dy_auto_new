from app.db_models import (
    Episode,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
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


def test_ai_audit_fallback_third_failure_triggers_image_backtrack(db, monkeypatch):
    series = Series(title="Audit Backtrack", logline="Audit", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": []},
    )
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1)
    db.add(prod_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(shot_plan_id=shot.id, segment_id="seg-1", order_index=1)
    db.add(segment)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=REAL_SHORT_E2E,
        status="image_batch_running",
        current_stage="image_generation",
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    for index, status in enumerate(["needs_human", "rejected"], start=1):
        prior = VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=segment.id,
            asset_type="image",
            stage="image_generation",
            url=f"https://cdn.test/old-{index}.png",
            version=index,
            status="rejected",
            production_segment_id=segment.id,
            target_type="production_segment",
            target_id=segment.id,
            is_latest=False,
        )
        db.add(prior)
        db.flush()
        db.add(VideoReviewRecord(
            asset_id=prior.id,
            run_id=run.id,
            review_type="ai",
            status=status,
            target_type="production_segment",
            target_id=segment.id,
            production_segment_id=segment.id,
            asset_version=prior.version,
            is_latest_asset_review=True,
        ))
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment.id,
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/current.png",
        version=3,
        status="review_pending",
        production_segment_id=segment.id,
        target_type="production_segment",
        target_id=segment.id,
        is_latest=True,
    )
    db.add(asset)
    db.commit()

    monkeypatch.setattr(
        "app.services.model_registry.get_model_for_scene",
        lambda db, scene: (_ for _ in ()).throw(RuntimeError("registry unavailable")),
    )
    monkeypatch.setattr(
        "app.services.video_production_service.resolve_runtime_model_config",
        lambda db, scene: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )

    run_ai_audit_for_assets(db, run, [asset])

    db.refresh(run)
    ai_review = db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="ai").one()
    job = db.query(ProductionJob).one()
    event = db.query(ProductionAuditEvent).filter_by(event_type="agency_backtrack_triggered").one()
    assert ai_review.status == "needs_human"
    assert job.stage == "agency_auto_repair:image_generation_failed"
    assert job.target_id == segment.id
    assert event.payload_json["backtrack_to"] == "storyboard"
    assert run.current_stage == "storyboard"
    assert run.status == "image_human_review_required"


def test_backtrack_state_survives_later_auto_approval_in_same_audit_batch(db, monkeypatch):
    series = Series(title="Audit Batch Backtrack", logline="Audit", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", storyboard_json={"frames": []})
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1)
    db.add(prod_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment_a = ProductionSegment(shot_plan_id=shot.id, segment_id="seg-a", order_index=1)
    segment_b = ProductionSegment(shot_plan_id=shot.id, segment_id="seg-b", order_index=2)
    db.add_all([segment_a, segment_b])
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=REAL_SHORT_E2E,
        status="image_batch_running",
        current_stage="image_generation",
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
        model_trace_json={"autopilot": {"enabled": True, "source": "test"}},
    )
    db.add(run)
    db.flush()
    for version in [1, 2]:
        prior = VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=segment_a.id,
            asset_type="image",
            stage="image_generation",
            url=f"https://cdn.test/fail-{version}.png",
            version=version,
            status="rejected",
            production_segment_id=segment_a.id,
            target_type="production_segment",
            target_id=segment_a.id,
            is_latest=False,
        )
        db.add(prior)
        db.flush()
        db.add(VideoReviewRecord(
            asset_id=prior.id,
            run_id=run.id,
            review_type="ai",
            status="needs_human",
            target_type="production_segment",
            target_id=segment_a.id,
            production_segment_id=segment_a.id,
            asset_version=prior.version,
            is_latest_asset_review=True,
        ))
    asset_a = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment_a.id,
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/fail-current.png",
        local_path="output/fail-current.png",
        storage_path="output/fail-current.png",
        checksum="fail-current",
        copy_status="persisted",
        version=3,
        status="review_pending",
        production_segment_id=segment_a.id,
        target_type="production_segment",
        target_id=segment_a.id,
        is_latest=True,
    )
    asset_b = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment_b.id,
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/pass-current.png",
        local_path="output/pass-current.png",
        storage_path="output/pass-current.png",
        checksum="pass-current",
        copy_status="persisted",
        version=1,
        status="review_pending",
        production_segment_id=segment_b.id,
        target_type="production_segment",
        target_id=segment_b.id,
        is_latest=True,
    )
    db.add_all([asset_a, asset_b])
    db.commit()

    monkeypatch.setattr(
        "app.services.video_production_service.resolve_runtime_model_config",
        lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"},
    )
    monkeypatch.setattr(
        "app.routers.audit._do_audit",
        lambda model, url, text: (
            {"score": 0.1, "pass_fail": False, "issues": ["bad"]}
            if "fail-current" in url
            else {"score": 0.99, "pass_fail": True, "issues": []}
        ),
    )

    run_ai_audit_for_assets(db, run, [asset_a, asset_b])

    db.refresh(run)
    db.refresh(asset_b)
    assert db.query(ProductionJob).filter_by(stage="agency_auto_repair:image_generation_failed").count() == 1
    assert asset_b.status == "approved"
    assert run.status == "image_human_review_required"
    assert run.current_stage == "storyboard"
