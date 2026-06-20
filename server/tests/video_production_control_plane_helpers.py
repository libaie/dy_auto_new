from app.db.models import (
    Episode,
    ProductionCostEvent,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
)


def linked_segment_context(db, *, segment_status="failed_retryable"):
    series = Series(title="Detail", logline="Detail", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, current_cost=0.02)
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready")
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-1",
        order_index=1,
        status="ready",
        duration_seconds=8,
    )
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-01",
        order_index=1,
        status=segment_status,
        duration_seconds=8,
        image_prompt="image",
        video_prompt="video",
        reference_roles_json=[],
    )
    db.add(segment)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment.id,
        asset_type="image",
        stage="image_generation",
        production_segment_id=segment.id,
        production_shot_id=shot.id,
        target_type="production_segment",
        target_id=segment.id,
        version=1,
        is_latest=True,
        source_version=segment.version,
        status="approved",
        url="https://example.test/image.png",
    )
    db.add(asset)
    db.add(ProductionCostEvent(
        plan_id=plan.id,
        episode_plan_id=production_episode.id,
        segment_id=segment.id,
        stage="image_generation",
        actual_cost=0.02,
        provider="mock",
        model_name="mock-image",
    ))
    db.commit()
    return {
        "series": series,
        "episode": episode,
        "plan": plan,
        "production_episode": production_episode,
        "scene": scene,
        "shot": shot,
        "segment": segment,
        "run": run,
        "asset": asset,
    }
