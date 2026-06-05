from fastapi.testclient import TestClient

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
from app.main import app
from app.services.production_status import SEGMENT_RETRY_QUEUED, SEGMENT_SUPERSEDED
from app.services.video_production_run_types import MOCK_SERIES_SCALE


client = TestClient(app)


def _create_tree_context(db):
    series = Series(title="Tree Show", logline="Tree", genre="drama")
    db.add(series)
    db.flush()

    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "seg-001"}, {"frame_id": "seg-002"}]},
    )
    db.add(episode)
    db.flush()

    plan = ProductionPlan(
        series_id=series.id,
        status="running",
        target_total_duration_seconds=60,
        budget_limit=25.0,
        current_cost=7.5,
    )
    other_plan = ProductionPlan(
        series_id=series.id,
        status="running",
        target_total_duration_seconds=30,
        budget_limit=10.0,
        current_cost=2.0,
    )
    db.add_all([plan, other_plan])
    db.flush()

    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=60,
    )
    other_episode = ProductionEpisode(
        plan_id=other_plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=30,
    )
    db.add_all([production_episode, other_episode])
    db.flush()

    scene = ProductionScene(
        episode_plan_id=production_episode.id,
        scene_id="scene-a",
        order_index=1,
        status="ready",
        location_summary="Street",
    )
    other_scene = ProductionScene(
        episode_plan_id=other_episode.id,
        scene_id="scene-other",
        order_index=1,
        status="ready",
    )
    db.add_all([scene, other_scene])
    db.flush()

    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-a",
        order_index=1,
        status="ready",
        action="walk",
        duration_seconds=15,
    )
    other_shot = ProductionShot(
        scene_plan_id=other_scene.id,
        shot_id="shot-other",
        order_index=1,
        status="ready",
        action="other",
        duration_seconds=5,
    )
    db.add_all([shot, other_shot])
    db.flush()

    segments = [
        ProductionSegment(
            shot_plan_id=shot.id,
            segment_id="seg-001",
            order_index=1,
            status="failed",
            duration_seconds=5.0,
            continuity_mode="continuous_action",
            version=1,
        ),
        ProductionSegment(
            shot_plan_id=shot.id,
            segment_id="seg-002",
            order_index=2,
            status="completed",
            duration_seconds=5.0,
            continuity_mode="narrative_cut",
            version=1,
        ),
        ProductionSegment(
            shot_plan_id=shot.id,
            segment_id="seg-003",
            order_index=3,
            status="video_review_pending",
            duration_seconds=5.0,
            continuity_mode="narrative_cut",
            version=1,
        ),
    ]
    db.add_all(segments)
    db.add(ProductionSegment(
        shot_plan_id=other_shot.id,
        segment_id="other-failed",
        order_index=1,
        status="failed",
        duration_seconds=5.0,
        continuity_mode="narrative_cut",
        version=1,
    ))
    db.commit()

    return {
        "series": series,
        "episode": episode,
        "plan": plan,
        "segments": segments,
    }


def _create_review_context(db, frame_ids=("seg-001",)):
    series = Series(title="Bulk API Show", logline="Bulk", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": frame_id} for frame_id in frame_ids]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        run_type=MOCK_SERIES_SCALE,
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    return run


def _asset(db, run, frame_id, asset_type, version, status="review_pending"):
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=frame_id,
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url=f"https://cdn.test/{frame_id}-{asset_type}-{version}",
        version=version,
        status=status,
        copy_status="persisted",
        checksum=f"checksum-{frame_id}-{asset_type}-{version}",
        storage_path=f"output/{frame_id}-{asset_type}-{version}",
    )
    db.add(asset)
    db.commit()
    return asset


def test_tree_endpoint_returns_hierarchy_pagination_and_plan_total(db):
    context = _create_tree_context(db)
    plan = context["plan"]

    resp = client.get(f"/api/video-production/plans/{plan.id}/tree", params={"page": 1, "page_size": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["plan"] == {
        "id": plan.id,
        "series_id": plan.series_id,
        "status": "running",
        "current_cost": 7.5,
        "budget_limit": 25.0,
    }
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total_segments"] == 3

    episode = body["episodes"][0]
    scene = episode["scenes"][0]
    shot = scene["shots"][0]
    returned_segments = shot["segments"]
    assert episode["episode_id"] == context["episode"].id
    assert scene["scene_id"] == "scene-a"
    assert shot["shot_id"] == "shot-a"
    assert [segment["segment_id"] for segment in returned_segments] == ["seg-001", "seg-002"]
    assert returned_segments[0]["status"] == "failed"
    assert returned_segments[0]["duration_seconds"] == 5.0
    assert returned_segments[0]["continuity_mode"] == "continuous_action"
    assert returned_segments[0]["version"] == 1


def test_tree_endpoint_filters_segment_status_with_plan_scoped_total(db):
    context = _create_tree_context(db)
    plan = context["plan"]

    resp = client.get(
        f"/api/video-production/plans/{plan.id}/tree",
        params={"status": "failed", "page": 1, "page_size": 50},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_segments"] == 1
    segments = body["episodes"][0]["scenes"][0]["shots"][0]["segments"]
    assert [segment["segment_id"] for segment in segments] == ["seg-001"]


def test_tree_endpoint_returns_404_for_missing_plan(db):
    resp = client.get("/api/video-production/plans/missing-plan/tree")

    assert resp.status_code == 404


def test_run_tree_endpoint_resolves_video_run_to_plan(db):
    context = _create_tree_context(db)
    series = context["series"]
    episode = context["episode"]
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        storyboard_json=episode.storyboard_json,
        model_trace_json={"production_plan_id": context["plan"].id},
    )
    db.add(run)
    db.commit()

    resp = client.get(f"/api/video-production/runs/{run.id}/tree", params={"page": 1, "page_size": 50})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["plan"]["id"] == context["plan"].id
    assert body["total_segments"] == 3


def test_tree_endpoint_exposes_segment_jobs_and_latest_assets(db):
    context = _create_tree_context(db)
    plan = context["plan"]
    segment = context["segments"][0]
    run = VideoProductionRun(
        series_id=context["series"].id,
        episode_id=context["episode"].id,
        status="image_batch_running",
        current_stage="image_generation",
        production_plan_id=plan.id,
        production_episode_id=db.query(ProductionEpisode).filter_by(plan_id=plan.id).one().id,
        production_link_status="linked",
        storyboard_json=context["episode"].storyboard_json,
    )
    db.add(run)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="image_generation",
        status="queued",
        idempotency_key=f"{run.id}:{segment.id}:image_generation:v1",
    )
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=segment.id,
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/seg-001-image.png",
        version=1,
        status="review_pending",
        production_segment_id=segment.id,
        target_type="production_segment",
        target_id=segment.id,
        is_latest=True,
        copy_status="persisted",
        checksum="checksum-seg-001-image",
        storage_path="output/seg-001-image.png",
    )
    db.add_all([job, asset])
    db.commit()

    resp = client.get(f"/api/video-production/runs/{run.id}/tree", params={"page": 1, "page_size": 50})

    assert resp.status_code == 200
    segment_payload = resp.json()["episodes"][0]["scenes"][0]["shots"][0]["segments"][0]
    assert segment_payload["stored_status"] == "failed"
    assert segment_payload["jobs"]["image_generation"]["status"] == "queued"
    assert segment_payload["jobs"]["image_generation"]["id"] == job.id
    assert segment_payload["latest_assets"]["image"]["id"] == asset.id
    assert segment_payload["latest_assets"]["image"]["url"] == "https://cdn.test/seg-001-image.png"


def test_tree_endpoint_derives_status_from_queued_job_for_existing_planned_segments(db):
    context = _create_tree_context(db)
    plan = context["plan"]
    segment = context["segments"][0]
    segment.status = "planned"
    run = VideoProductionRun(
        series_id=context["series"].id,
        episode_id=context["episode"].id,
        status="image_batch_running",
        current_stage="image_generation",
        production_plan_id=plan.id,
        production_episode_id=db.query(ProductionEpisode).filter_by(plan_id=plan.id).one().id,
        production_link_status="linked",
        storyboard_json=context["episode"].storyboard_json,
    )
    db.add(run)
    db.flush()
    db.add(ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="image_generation",
        status="queued",
        idempotency_key=f"{run.id}:{segment.id}:image_generation:v1",
    ))
    db.commit()

    resp = client.get(f"/api/video-production/runs/{run.id}/tree", params={"page": 1, "page_size": 50})

    assert resp.status_code == 200
    segment_payload = resp.json()["episodes"][0]["scenes"][0]["shots"][0]["segments"][0]
    assert segment_payload["stored_status"] == "planned"
    assert segment_payload["status"] == "image_queued"


def test_tree_endpoint_derives_blocked_status_from_blocked_job(db):
    context = _create_tree_context(db)
    plan = context["plan"]
    segment = context["segments"][0]
    segment.status = "image_running"
    run = VideoProductionRun(
        series_id=context["series"].id,
        episode_id=context["episode"].id,
        status="image_human_review_required",
        current_stage="image_review",
        production_plan_id=plan.id,
        production_episode_id=db.query(ProductionEpisode).filter_by(plan_id=plan.id).one().id,
        production_link_status="linked",
        storyboard_json=context["episode"].storyboard_json,
    )
    db.add(run)
    db.flush()
    db.add(ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="image_generation",
        status="blocked",
        idempotency_key=f"{run.id}:{segment.id}:image_generation:v1",
    ))
    db.commit()

    resp = client.get(f"/api/video-production/runs/{run.id}/tree", params={"page": 1, "page_size": 50})

    assert resp.status_code == 200
    segment_payload = resp.json()["episodes"][0]["scenes"][0]["shots"][0]["segments"][0]
    assert segment_payload["stored_status"] == "image_running"
    assert segment_payload["status"] == "blocked_by_review"


def test_run_tree_endpoint_rejects_ambiguous_unlinked_run(db):
    context = _create_tree_context(db)
    series = context["series"]
    episode = context["episode"]
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()

    resp = client.get(f"/api/video-production/runs/{run.id}/tree", params={"page": 1, "page_size": 50})

    assert resp.status_code == 409


def test_run_tree_endpoint_rejects_mismatched_traced_plan(db):
    context = _create_tree_context(db)
    other_series = Series(title="Other", logline="Other", genre="drama")
    db.add(other_series)
    db.flush()
    other_episode = Episode(series_id=other_series.id, episode_number=1, title="Other")
    db.add(other_episode)
    db.flush()
    run = VideoProductionRun(
        series_id=other_series.id,
        episode_id=other_episode.id,
        status="image_review_pending",
        current_stage="image_review",
        storyboard_json={"frames": [{"frame_id": "seg-001"}]},
        model_trace_json={"production_plan_id": context["plan"].id},
    )
    db.add(run)
    db.commit()

    resp = client.get(f"/api/video-production/runs/{run.id}/tree")

    assert resp.status_code == 409


def test_tree_endpoint_does_not_return_empty_parents_for_filtered_segments(db):
    context = _create_tree_context(db)
    plan = context["plan"]
    production_episode = db.query(ProductionEpisode).filter_by(plan_id=plan.id).one()
    scene = ProductionScene(
        episode_plan_id=production_episode.id,
        scene_id="scene-b",
        order_index=2,
        status="ready",
    )
    db.add(scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-b",
        order_index=2,
        status="ready",
        action="cutaway",
        duration_seconds=5,
    )
    db.add(shot)
    db.flush()
    db.add(ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-004",
        order_index=1,
        status="completed",
        duration_seconds=5,
        continuity_mode="narrative_cut",
    ))
    db.commit()

    resp = client.get(
        f"/api/video-production/plans/{plan.id}/tree",
        params={"status": "failed", "page": 1, "page_size": 50},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_segments"] == 1
    assert len(body["episodes"]) == 1
    assert len(body["episodes"][0]["scenes"]) == 1
    assert body["episodes"][0]["scenes"][0]["scene_id"] == "scene-a"


def test_retry_endpoint_returns_new_segment_version(db):
    context = _create_tree_context(db)
    failed_segment = context["segments"][0]

    resp = client.post(f"/api/video-production/segments/{failed_segment.id}/retry")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["segment"]["id"] != failed_segment.id
    assert body["segment"]["segment_id"] == failed_segment.segment_id
    assert body["segment"]["version"] == 2
    assert body["segment"]["status"] == SEGMENT_RETRY_QUEUED
    db.refresh(failed_segment)
    assert failed_segment.status == SEGMENT_SUPERSEDED


def test_retry_endpoint_returns_400_for_missing_segment(db):
    resp = client.post("/api/video-production/segments/missing-segment/retry")

    assert resp.status_code == 404


def test_retry_endpoint_returns_409_for_non_retryable_segment(db):
    context = _create_tree_context(db)
    completed_segment = context["segments"][1]

    resp = client.post(f"/api/video-production/segments/{completed_segment.id}/retry")

    assert resp.status_code == 409


def test_bulk_review_endpoint_approves_latest_only_and_returns_counts(db):
    run = _create_review_context(db)
    old_asset = _asset(db, run, "seg-001", "image", 1)
    latest_asset = _asset(db, run, "seg-001", "image", 2)

    resp = client.post("/api/video-production/reviews/bulk-action", json={
        "asset_ids": [old_asset.id, latest_asset.id],
        "action": "approve",
        "comment": "bulk approve",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["result"] == {"approved": 1, "rejected": 0, "skipped_stale": 1}
    db.refresh(old_asset)
    db.refresh(latest_asset)
    assert old_asset.status == "review_pending"
    assert latest_asset.status == "approved"
    review = db.query(VideoReviewRecord).filter_by(asset_id=latest_asset.id, review_type="human").one()
    assert review.reviewer_user_id == "test-user-id"
    assert review.comment == "bulk approve"


def test_bulk_review_endpoint_returns_400_for_unsupported_action(db):
    run = _create_review_context(db)
    asset = _asset(db, run, "seg-001", "image", 1)

    resp = client.post("/api/video-production/reviews/bulk-action", json={
        "asset_ids": [asset.id],
        "action": "hold",
        "comment": "not supported",
    })

    assert resp.status_code == 400


def test_bulk_review_endpoint_returns_400_for_final_video(db):
    run = _create_review_context(db)
    asset = _asset(db, run, "seg-001", "final_video", 1)

    resp = client.post("/api/video-production/reviews/bulk-action", json={
        "asset_ids": [asset.id],
        "action": "approve",
    })

    assert resp.status_code == 400
