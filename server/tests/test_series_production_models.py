from app.db.models import (
    Episode,
    ProductionCostEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoCollection,
    VideoProductionAsset,
    VideoProductionRun,
)


def test_series_production_model_graph_can_persist(db):
    series = Series(title="Long Show", logline="A test show", genre="drama", target_duration=300)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()

    plan = ProductionPlan(
        series_id=series.id,
        status="ready",
        target_total_duration_seconds=300,
        active_version=1,
        budget_limit=100.0,
        current_cost=0.0,
    )
    db.add(plan)
    db.flush()
    version = ProductionPlanVersion(
        plan_id=plan.id,
        version=1,
        style_lock_json={"locked": True, "version": 1},
        model_config_snapshot_json={"image_generation": {"model": "doubao-seedream-5.0-lite"}},
        prompt_policy_json={"continuity": "typed_reference_roles"},
    )
    db.add(version)
    prod_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=180,
    )
    db.add(prod_episode)
    db.flush()
    scene = ProductionScene(
        episode_plan_id=prod_episode.id,
        scene_id="scene-a",
        order_index=1,
        status="ready",
        location_summary="Night street",
    )
    db.add(scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-a",
        order_index=1,
        status="ready",
        character_ids=["char-a"],
        action="turns around",
        emotion="tense",
        shot_type="medium",
        duration_seconds=8,
    )
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-a",
        order_index=1,
        status="planned",
        duration_seconds=5,
        continuity_mode="continuous_action",
        version=1,
        previous_segment_id=None,
        previous_end_frame_url="https://cdn.test/previous.png",
        expected_end_state="character turned toward camera",
        retry_count=1,
        image_prompt="street still frame",
        video_prompt="slow push-in",
        narration="A quiet turn.",
        reference_roles_json=[{"role": "character_anchor", "url": "https://cdn.test/char.png", "priority": 1}],
    )
    db.add(segment)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="segment",
        target_id=segment.id,
        stage="image_generation",
        status="queued",
        provider_task_id="provider-task-1",
        attempt_count=1,
        max_attempts=3,
        lease_id="lease-1",
        priority=50,
        idempotency_key=f"{segment.id}:image_generation:v1",
    )
    db.add(job)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="draft",
        current_stage="image_generation",
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="seg-a",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/image.png",
        version=1,
        status="review_pending",
        production_segment_id=segment.id,
    )
    db.add(asset)
    cost = ProductionCostEvent(
        plan_id=plan.id,
        episode_plan_id=prod_episode.id,
        segment_id=segment.id,
        stage="image_generation",
        model_config_id="config-1",
        config_version=2,
        provider_task_id="provider-task-1",
        provider="seedance",
        model_name="doubao-seedream-5.0-lite",
        estimated_cost=0.2,
        actual_cost=0.0,
        currency="CNY",
        units_json={"images": 1},
    )
    db.add(cost)
    collection = VideoCollection(
        series_id=series.id,
        status="draft",
        included_episode_ids=[episode.id],
        duration_seconds=0,
        video_url="https://cdn.test/final.mp4",
        error_message=None,
    )
    db.add(collection)
    db.commit()

    assert db.query(ProductionPlan).filter_by(series_id=series.id).count() == 1
    saved_segment = db.query(ProductionSegment).filter_by(segment_id="seg-a").one()
    assert saved_segment.version == 1
    assert saved_segment.previous_end_frame_url == "https://cdn.test/previous.png"
    assert saved_segment.retry_count == 1
    assert saved_segment.image_prompt == "street still frame"
    assert saved_segment.video_prompt == "slow push-in"
    assert saved_segment.narration == "A quiet turn."
    saved_job = db.query(ProductionJob).filter_by(idempotency_key=f"{segment.id}:image_generation:v1").one()
    assert saved_job.status == "queued"
    assert saved_job.provider_task_id == "provider-task-1"
    assert saved_job.attempt_count == 1
    assert saved_job.max_attempts == 3
    assert saved_job.lease_id == "lease-1"
    assert saved_job.priority == 50
    assert saved_job.retryable is True
    saved_cost = db.query(ProductionCostEvent).filter_by(segment_id=segment.id).one()
    assert saved_cost.model_config_id == "config-1"
    assert saved_cost.config_version == 2
    assert saved_cost.provider_task_id == "provider-task-1"
    assert saved_cost.provider == "seedance"
    assert db.query(VideoProductionAsset).filter_by(production_segment_id=segment.id).one().frame_id == "seg-a"
    saved_collection = db.query(VideoCollection).filter_by(series_id=series.id).one()
    assert saved_collection.included_episode_ids == [episode.id]
    assert saved_collection.video_url == "https://cdn.test/final.mp4"
    assert saved_collection.error_message is None
