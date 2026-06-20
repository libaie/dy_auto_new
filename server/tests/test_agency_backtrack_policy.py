from app.db.models import (
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
from app.domains.agency_operations.agency_backtrack_policy import trigger_backtrack_if_needed
from app.domains.video_production.production_queue_service import claim_next_job, mark_job_completed
from app.domains.video_production.production_status import JOB_COMPLETED


def test_auto_repair_stage_names_fit_production_job_stage_column():
    stage_length = ProductionJob.__table__.c.stage.type.length
    stage_names = [
        "agency_auto_repair:image_generation_failed",
        "agency_auto_repair:image_generation_timeout",
        "agency_auto_repair:storyboard_missing_references",
        "agency_auto_repair:missing_character_reference",
        "agency_auto_repair:missing_scene_reference",
        "agency_auto_repair:video_segment_failed",
        "agency_auto_repair:video_segment_timeout",
    ]

    assert max(len(stage_name) for stage_name in stage_names) <= stage_length


def _linked_run_with_segment(db):
    series = Series(title="Backtrack", logline="case", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, storyboard_json={"frames": []})
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
        status="video_review_pending",
        current_stage="video_review",
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    return series, episode, plan, prod_episode, segment, run


def _reviewed_asset(
    db,
    run,
    episode,
    segment,
    *,
    asset_type: str,
    version: int,
    status: str = "rejected",
    is_latest: bool = False,
) -> VideoProductionAsset:
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment.id,
        asset_type=asset_type,
        stage="video_generation" if asset_type == "video_segment" else "image_generation",
        status="review_pending" if is_latest else "rejected",
        production_segment_id=segment.id,
        target_type="production_segment",
        target_id=segment.id,
        version=version,
        is_latest=is_latest,
    )
    db.add(asset)
    db.flush()
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=run.id,
        review_type="human",
        status=status,
        target_type="production_segment",
        target_id=segment.id,
        production_segment_id=segment.id,
        asset_version=asset.version,
        is_latest_asset_review=True,
    ))
    db.flush()
    return asset


def test_third_video_failure_enqueues_backtrack_to_image_generation(db):
    _series, episode, plan, _prod_episode, segment, run = _linked_run_with_segment(db)
    _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=1)
    _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=2)
    asset = _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=3, is_latest=True)
    db.commit()

    result = trigger_backtrack_if_needed(db, run, asset, reason="video failed repeatedly")

    job = db.query(ProductionJob).one()
    event = db.query(ProductionAuditEvent).filter_by(event_type="agency_backtrack_triggered").one()
    claimed = claim_next_job(db, "test-lease", plan_id=plan.id)
    assert result["triggered"] is True
    assert job.stage == "agency_auto_repair:video_segment_failed"
    assert job.target_id == segment.id
    assert claimed.id == job.id
    assert event.payload_json["backtrack_to"] == "image_generation"
    assert run.status == "image_batch_running"


def test_backtrack_helper_flushes_without_committing_internally(db, monkeypatch):
    _series, episode, plan, _prod_episode, segment, run = _linked_run_with_segment(db)
    _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=1)
    _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=2)
    asset = _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=3, is_latest=True)
    db.commit()
    commit_calls = []

    def fake_commit():
        commit_calls.append(True)

    monkeypatch.setattr(db, "commit", fake_commit)

    result = trigger_backtrack_if_needed(db, run, asset, reason="video failed repeatedly")

    assert result["triggered"] is True
    assert commit_calls == []
    assert db.query(ProductionJob).filter_by(plan_id=plan.id).count() == 1
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_backtrack_triggered").count() == 1


def test_second_image_failure_does_not_backtrack(db):
    _series, episode, _plan, _prod_episode, segment, run = _linked_run_with_segment(db)
    _reviewed_asset(db, run, episode, segment, asset_type="image", version=1, status="needs_human")
    asset = _reviewed_asset(db, run, episode, segment, asset_type="image", version=2, is_latest=True)
    db.commit()

    result = trigger_backtrack_if_needed(db, run, asset, reason="not enough failures")

    assert result["triggered"] is False
    assert db.query(ProductionJob).count() == 0


def test_multiple_reviews_for_one_asset_count_as_one_failed_generation_attempt(db):
    _series, episode, _plan, _prod_episode, segment, run = _linked_run_with_segment(db)
    asset = _reviewed_asset(db, run, episode, segment, asset_type="image", version=1, status="needs_human", is_latest=True)
    for status in ["rejected", "failed"]:
        db.add(VideoReviewRecord(
            asset_id=asset.id,
            run_id=run.id,
            review_type="human",
            status=status,
            target_type="production_segment",
            target_id=segment.id,
            production_segment_id=segment.id,
            asset_version=asset.version,
            is_latest_asset_review=True,
        ))
    db.commit()

    result = trigger_backtrack_if_needed(db, run, asset, reason="same asset reviewed repeatedly")

    assert result["triggered"] is False
    assert result["failure_count"] == 1
    assert db.query(ProductionJob).count() == 0


def test_completed_backtrack_job_does_not_dedupe_next_failure_cycle(db):
    _series, episode, plan, _prod_episode, segment, run = _linked_run_with_segment(db)
    _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=1)
    _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=2)
    first_latest = _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=3, is_latest=True)
    db.commit()

    first = trigger_backtrack_if_needed(db, run, first_latest, reason="first failure cycle")
    first_job = db.query(ProductionJob).filter_by(id=first["job_id"]).one()
    mark_job_completed(db, first_job.id, allowed_statuses=("queued",))
    first_latest.is_latest = False
    _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=4)
    _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=5)
    second_latest = _reviewed_asset(db, run, episode, segment, asset_type="video_segment", version=6, is_latest=True)
    db.commit()

    second = trigger_backtrack_if_needed(db, run, second_latest, reason="second failure cycle")

    jobs = db.query(ProductionJob).order_by(ProductionJob.created_at.asc()).all()
    assert first_job.status == JOB_COMPLETED
    assert second["triggered"] is True
    assert second["job_id"] != first["job_id"]
    assert len(jobs) == 2
    assert claim_next_job(db, "second-cycle", plan_id=plan.id).id == second["job_id"]
