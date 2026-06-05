from app import db_models as models
from app.db_models import (
    Episode,
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


def _linked_context(db):
    series = Series(title="Control Plane", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(
        series_id=series.id,
        status="ready",
        active_version=1,
        target_total_duration_seconds=8,
        current_cost=0.0,
    )
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=8,
    )
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(
        episode_plan_id=production_episode.id,
        scene_id="scene-1",
        order_index=1,
        status="ready",
    )
    db.add(scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-1",
        order_index=1,
        status="ready",
        character_ids=[],
        action="walk forward",
        shot_type="medium",
        duration_seconds=8,
    )
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-01",
        order_index=1,
        status="planned",
        duration_seconds=8,
        continuity_mode="narrative_cut",
        version=1,
        image_prompt="image prompt",
        video_prompt="video prompt",
        reference_roles_json=[],
    )
    db.add(segment)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id)
    db.add(run)
    db.flush()
    return {
        "series": series,
        "episode": episode,
        "plan": plan,
        "production_episode": production_episode,
        "shot": shot,
        "segment": segment,
        "run": run,
    }


def test_video_production_run_has_real_production_links(db):
    assert hasattr(VideoProductionRun, "production_plan_id")
    assert hasattr(VideoProductionRun, "production_episode_id")
    assert hasattr(VideoProductionRun, "production_link_status")

    ctx = _linked_context(db)
    run = ctx["run"]
    plan = ctx["plan"]
    production_episode = ctx["production_episode"]

    run.production_plan_id = plan.id
    run.production_episode_id = production_episode.id
    run.production_link_status = "linked"
    db.commit()

    saved = db.query(VideoProductionRun).filter_by(id=run.id).one()
    assert saved.production_plan_id == plan.id
    assert saved.production_episode_id == production_episode.id
    assert saved.production_link_status == "linked"


def test_asset_and_review_store_latest_version_truth(db):
    assert hasattr(VideoProductionAsset, "production_shot_id")
    assert hasattr(VideoProductionAsset, "is_latest")
    assert hasattr(VideoProductionAsset, "source_version")
    assert hasattr(VideoReviewRecord, "asset_version")
    assert hasattr(VideoReviewRecord, "is_latest_asset_review")

    ctx = _linked_context(db)
    run = VideoProductionRun(
        series_id=ctx["series"].id,
        episode_id=ctx["episode"].id,
        production_plan_id=ctx["plan"].id,
        production_episode_id=ctx["production_episode"].id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=ctx["episode"].id,
        frame_id=ctx["segment"].id,
        asset_type="image",
        stage="image_generation",
        production_segment_id=ctx["segment"].id,
        production_shot_id=ctx["shot"].id,
        target_type="production_segment",
        target_id=ctx["segment"].id,
        version=2,
        is_latest=True,
        source_version=2,
        copy_status="registered",
        checksum="sha256:test",
        size_bytes=12,
    )
    db.add(asset)
    db.flush()
    review = VideoReviewRecord(
        asset_id=asset.id,
        run_id=run.id,
        review_type="human",
        status="approved",
        target_type="production_segment",
        target_id=ctx["segment"].id,
        production_segment_id=ctx["segment"].id,
        asset_version=2,
        is_latest_asset_review=True,
    )
    db.add(review)
    db.commit()

    assert db.query(VideoProductionAsset).filter_by(id=asset.id).one().is_latest is True
    assert db.query(VideoReviewRecord).filter_by(id=review.id).one().asset_version == 2


def test_job_pause_resume_fields_and_audit_event(db):
    assert hasattr(ProductionJob, "resume_status")
    assert hasattr(ProductionJob, "blocked_reason")
    assert hasattr(models, "ProductionAuditEvent")

    ctx = _linked_context(db)
    job = ProductionJob(
        plan_id=ctx["plan"].id,
        target_type="production_segment",
        target_id=ctx["segment"].id,
        stage="image_generation",
        status="blocked",
        resume_status="queued",
        blocked_reason="PAUSED_BY_OPERATOR",
        idempotency_key="plan:seg:image:v1",
    )
    db.add(job)
    event = models.ProductionAuditEvent(
        event_type="run.created",
        run_id=ctx["run"].id,
        production_plan_id=ctx["plan"].id,
        production_episode_id=ctx["production_episode"].id,
        production_segment_id=ctx["segment"].id,
        payload_json={"redacted": True},
    )
    db.add(event)
    db.commit()

    assert db.query(ProductionJob).one().resume_status == "queued"
    assert db.query(models.ProductionAuditEvent).one().event_type == "run.created"
