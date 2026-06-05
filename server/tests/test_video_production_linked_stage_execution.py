from fastapi.testclient import TestClient

from app.db_models import (
    Episode,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    ProductionJob,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
)
from app.main import app
from app.services.video_production_run_types import REAL_SHORT_E2E

client = TestClient(app)


async def _agency_pass(*args, **kwargs):
    return {"stage_status": "passed", "invocation_ids": [], "invocations": []}


def _linked_run_with_segments(db, *, count=1, run_type=None, budget_limit=None):
    series = Series(title="Linked", logline="Linked", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, budget_limit=budget_limit)
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
        character_ids=["hero"],
        action="hero looks at the city",
        shot_type="medium",
        duration_seconds=8,
    )
    db.add(shot)
    db.flush()

    segments = []
    for index in range(1, count + 1):
        segment = ProductionSegment(
            shot_plan_id=shot.id,
            segment_id=f"shot-1-seg-{index:02d}",
            order_index=index,
            status="planned",
            duration_seconds=8 + index,
            continuity_mode="narrative_cut",
            version=1,
            expected_end_state=f"end state {index}",
            image_prompt=f"hero on rooftop {index}",
            video_prompt=f"slow push in {index}",
            narration=f"narration {index}",
            reference_roles_json=[{"role": "character_anchor", "url": f"https://example.test/hero-{index}.png"}],
        )
        db.add(segment)
        db.flush()
        segments.append(segment)

    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
        run_type=run_type or "legacy_episode_run",
        status="storyboard_ready",
        current_stage="storyboard_ready",
    )
    db.add(run)
    db.commit()
    return run, segments


def _legacy_run(db):
    series = Series(title="Legacy", logline="Legacy", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_link_status="legacy_unlinked",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "legacy prompt", "reference_urls": []}]},
    )
    db.add(run)
    db.commit()
    return run


def _asset(db, run, segment, *, asset_type, url, status="approved", version=1, is_latest=True):
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=segment.id,
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url=url,
        duration_seconds=segment.duration_seconds,
        version=version,
        status=status,
        copy_status="persisted",
        checksum=f"checksum-{segment.id}-{asset_type}-{version}",
        storage_path=f"output/{segment.id}-{asset_type}-{version}",
        production_segment_id=segment.id,
        target_type="production_segment",
        target_id=segment.id,
        source_version=segment.version,
        is_latest=is_latest,
    )
    db.add(asset)
    db.commit()
    return asset


def test_linked_run_image_frames_are_built_from_segments(db):
    from app.services.video_production_service import image_stage_frames

    run, segments = _linked_run_with_segments(db)
    segment = segments[0]

    frames = image_stage_frames(run, db=db)

    assert frames[0]["frame_id"] == segment.id
    assert frames[0]["production_segment_id"] == segment.id
    assert frames[0]["image_prompt"] == segment.image_prompt
    assert frames[0]["video_prompt"] == segment.video_prompt
    assert frames[0]["narration"] == segment.narration
    assert frames[0]["reference_urls"] == ["https://example.test/hero-1.png"]
    assert frames[0]["reference_instructions"]
    assert frames[0]["style_constraints"]["source_version"] == segment.version


def test_legacy_run_image_frames_still_use_storyboard(db):
    from app.services.video_production_service import image_stage_frames

    run = _legacy_run(db)

    frames = image_stage_frames(run)

    assert frames[0]["frame_id"] == "frame-001"
    assert frames[0]["image_prompt"] == "legacy prompt"
    assert "production_segment_id" not in frames[0]


def test_worker_image_job_spec_includes_redacted_provider_parameters(db, monkeypatch):
    from app.services.production_worker_service import _job_spec

    run, segments = _linked_run_with_segments(db, count=1, run_type=REAL_SHORT_E2E, budget_limit=1.0)
    client.post(f"/api/video-production/runs/{run.id}/start-images")
    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="image_generation").one()
    monkeypatch.setattr("app.services.production_worker_service.resolve_runtime_model_config", lambda db, scene: {
        "provider": "seedance",
        "model": "doubao-seedream-5.0-lite",
        "api_key": "secret-key",
        "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
        "config": {"default_size": "1440x2560"},
    })

    spec = _job_spec(db, run, job)

    frame = spec["payload"]["frame"]
    assert frame["provider_parameters"]["provider"] == "seedance"
    assert frame["provider_parameters"]["model"] == "doubao-seedream-5.0-lite"
    assert "api_key" not in frame["provider_parameters"]
    assert frame["style_constraints"]["continuity_notes"]


def test_linked_video_frames_use_approved_segment_image_and_video_prompt(db):
    from app.services.video_production_service import video_stage_frames

    run, segments = _linked_run_with_segments(db)
    segment = segments[0]
    _asset(db, run, segment, asset_type="image", url="https://cdn.test/approved-image.png")

    frames = video_stage_frames(db, run)

    assert frames[0]["frame_id"] == segment.id
    assert frames[0]["production_segment_id"] == segment.id
    assert frames[0]["approved_image_url"] == "https://cdn.test/approved-image.png"
    assert frames[0]["video_prompt"] == segment.video_prompt
    assert frames[0]["reference_urls"] == ["https://example.test/hero-1.png"]


def test_linked_compose_segments_use_ordered_production_segments(db):
    from app.services.video_production_service import compose_segments

    run, segments = _linked_run_with_segments(db, count=2)
    _asset(db, run, segments[1], asset_type="video_segment", url="https://cdn.test/segment-2.mp4")
    _asset(db, run, segments[0], asset_type="video_segment", url="https://cdn.test/segment-1.mp4")

    payload = compose_segments(db, run)

    assert [item["frame_id"] for item in payload] == [segments[0].id, segments[1].id]
    assert [item["video_url"] for item in payload] == [
        f"output/{segments[0].id}-video_segment-1",
        f"output/{segments[1].id}-video_segment-1",
    ]
    assert payload[0]["narration"] == segments[0].narration


def test_linked_image_asset_write_demotes_previous_latest_for_segment(db):
    from app.services.video_production_service import mark_image_stage_assets

    run, segments = _linked_run_with_segments(db)
    segment = segments[0]
    old = _asset(db, run, segment, asset_type="image", url="https://cdn.test/old-image.png")

    saved = mark_image_stage_assets(
        db,
        run,
        [{
            "frame_id": segment.id,
            "production_segment_id": segment.id,
            "source_version": segment.version,
            "url": "https://cdn.test/new-image.png",
            "provider_task_id": "provider-image-2",
            "metadata": {},
        }],
        pixelle_task_id="image-task-2",
    )

    db.refresh(old)
    assert old.is_latest is False
    assert saved[0].production_segment_id == segment.id
    assert saved[0].target_type == "production_segment"
    assert saved[0].target_id == segment.id
    assert saved[0].source_version == segment.version
    assert saved[0].is_latest is True
    assert saved[0].version == 2


def test_real_short_start_images_route_enqueues_jobs_without_legacy_submit(db, monkeypatch):
    run, segments = _linked_run_with_segments(db, count=2, run_type=REAL_SHORT_E2E, budget_limit=1.0)
    async def fail_legacy_submit(*args, **kwargs):
        raise AssertionError("legacy image batch submit must not run for real_short_e2e")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fail_legacy_submit)

    response = client.post(f"/api/video-production/runs/{run.id}/start-images")

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["status"] == "image_batch_running"
    jobs = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="image_generation").all()
    assert {job.target_id for job in jobs} == {segment.id for segment in segments}
    assert len(jobs) == 2
    for segment in segments:
        db.refresh(segment)
    assert {segment.status for segment in segments} == {"image_queued"}

    second = client.post(f"/api/video-production/runs/{run.id}/start-images")
    assert second.status_code == 400
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="image_generation").count() == 2


def test_real_short_start_images_defers_image_stage_agency_gate_to_worker(db, monkeypatch):
    run, _segments = _linked_run_with_segments(db, count=1, run_type=REAL_SHORT_E2E, budget_limit=1.0)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("real_short_e2e start-images must not synchronously run agency review")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", fail_if_called)

    response = client.post(f"/api/video-production/runs/{run.id}/start-images")

    assert response.status_code == 200
    assert response.json()["run"]["status"] == "image_batch_running"
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="image_generation").count() == 1


def test_real_worker_runs_deferred_image_stage_agency_gate_before_provider_submit(db, monkeypatch):
    from app.services.production_worker_service import run_real_worker_step

    run, _segments = _linked_run_with_segments(db, count=1, run_type=REAL_SHORT_E2E, budget_limit=1.0)
    client.post(f"/api/video-production/runs/{run.id}/start-images")
    guarded_stages = []

    async def block_image_stage(db, run, stage, stage_context):
        guarded_stages.append(stage)
        return None

    async def fail_submit(*args, **kwargs):
        raise AssertionError("provider submit must not run when deferred agency gate blocks")

    def fake_runtime_config(db, scene):
        return {
        "provider": "test",
        "model_name": scene,
        "api_key": "test-key",
        "config": {},
        }

    monkeypatch.setattr("app.services.production_worker_service.resolve_runtime_model_config", fake_runtime_config)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", fake_runtime_config)
    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", block_image_stage)
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fail_submit)

    result = run_real_worker_step(db, run.id, lease_id="test-worker", batch_size=1)

    assert guarded_stages == ["image_stage"]
    assert result["processed"] == 1
    assert result["items"][0]["status"] == "blocked"
    db.refresh(run)
    assert run.status == "image_human_review_required"
    assert run.current_stage == "image_review"
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="image_generation", status="blocked").count() == 1
    segment = db.query(ProductionSegment).filter_by(id=_segments[0].id).one()
    assert segment.status == "blocked_by_review"


def test_real_worker_continues_provider_submit_when_deferred_agency_gate_times_out(db, monkeypatch):
    import asyncio
    from app.services.production_worker_service import run_real_worker_step

    run, segments = _linked_run_with_segments(db, count=1, run_type=REAL_SHORT_E2E, budget_limit=1.0)
    client.post(f"/api/video-production/runs/{run.id}/start-images")
    submitted = {}

    async def slow_gate(*args, **kwargs):
        await asyncio.sleep(1)
        return {"stage_status": "passed"}

    async def submit_image(db, run_id, episode_id, frames, model_config, template_config=None):
        submitted["frames"] = frames
        return {"ok": True, "stage_task_id": "image-task-timeout-continue"}

    async def get_stage_task(db, stage_task_id):
        frame = submitted["frames"][0]
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": frame["production_segment_id"],
                "production_segment_id": frame["production_segment_id"],
                "url": "https://cdn.test/timeout-continue.png",
                "source_url": "https://cdn.test/timeout-continue.png",
                "metadata": {"duration": frame["duration"]},
            }],
            "usage": {"cost": 0.01, "units": {"images": 1}},
        }

    monkeypatch.setattr("app.services.production_worker_service.DEFERRED_STAGE_GATE_TIMEOUT_SECONDS", 0.01)
    def fake_runtime_config(db, scene):
        return {
        "provider": "test",
        "model_name": scene,
        "api_key": "test-key",
        "config": {
            "real_paid_allowed": True,
            "supports_external_task_id": True,
            "supports_task_query": True,
            "returns_asset_url": True,
            "returns_usage": True,
            "estimated_cost": 0.01,
            "max_concurrent_tasks": 1,
        },
        }

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    monkeypatch.setattr("app.services.production_worker_service.resolve_runtime_model_config", fake_runtime_config)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", fake_runtime_config)
    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", slow_gate)
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", submit_image)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", get_stage_task)

    result = run_real_worker_step(db, run.id, lease_id="test-worker", batch_size=1)

    assert result["processed"] == 1
    assert result["items"][0]["ok"] is True
    assert submitted["frames"][0]["production_segment_id"] == segments[0].id
    refreshed = db.query(VideoProductionRun).filter_by(id=run.id).one()
    trace = refreshed.model_trace_json["agency_reviews"]["image_stage"]
    assert trace["stage_status"] == "partial"
    assert trace["error_code"] == "DEFERRED_STAGE_REVIEW_TIMEOUT"
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="image_generation", status="completed").count() == 1
    assert db.query(VideoProductionAsset).filter_by(run_id=run.id, asset_type="image").count() == 1


def test_legacy_start_images_blocks_paid_model_direct_submit(db, monkeypatch):
    run, _segments = _linked_run_with_segments(db, count=1)

    async def fail_legacy_submit(*args, **kwargs):
        raise AssertionError("legacy paid provider submit must be blocked before direct submit")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr(
        "app.services.video_production_service.resolve_runtime_model_config",
        lambda db, scene: {
            "provider": "seedance",
            "model": scene,
            "config": {
                "real_paid_allowed": True,
                "supports_external_task_id": True,
                "supports_task_query": True,
                "returns_asset_url": True,
                "returns_usage": True,
                "estimated_cost": 0.01,
                "supports_text_to_image": True,
            },
        },
    )
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fail_legacy_submit)

    response = client.post(f"/api/video-production/runs/{run.id}/start-images")

    assert response.status_code == 400
    assert "legacy_episode_run cannot submit paid provider scene" in response.json()["detail"]


def test_real_short_start_videos_route_enqueues_jobs_without_legacy_submit(db, monkeypatch):
    run, segments = _linked_run_with_segments(db, run_type=REAL_SHORT_E2E, budget_limit=1.0)
    for segment in segments:
        _asset(db, run, segment, asset_type="image", url=f"https://cdn.test/{segment.id}.png")
    run.status = "image_approved"
    db.commit()

    async def fail_legacy_submit(*args, **kwargs):
        raise AssertionError("legacy video batch submit must not run for real_short_e2e")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fail_legacy_submit)

    response = client.post(f"/api/video-production/runs/{run.id}/start-videos")

    assert response.status_code == 200
    assert response.json()["run"]["status"] == "video_batch_running"
    jobs = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="video_generation").all()
    assert {job.target_id for job in jobs} == {segment.id for segment in segments}


def test_real_short_start_videos_defers_video_stage_agency_gate_to_worker(db, monkeypatch):
    run, segments = _linked_run_with_segments(db, run_type=REAL_SHORT_E2E, budget_limit=1.0)
    for segment in segments:
        _asset(db, run, segment, asset_type="image", url=f"https://cdn.test/{segment.id}.png")
    run.status = "image_approved"
    db.commit()
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("real_short_e2e start-videos must not synchronously run agency review")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", fail_if_called)

    response = client.post(f"/api/video-production/runs/{run.id}/start-videos")

    assert response.status_code == 200
    assert response.json()["run"]["status"] == "video_batch_running"
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="video_generation").count() == len(segments)


def test_real_short_compose_route_enqueues_job_without_legacy_submit(db, monkeypatch):
    run, segments = _linked_run_with_segments(db, run_type=REAL_SHORT_E2E, budget_limit=1.0)
    for segment in segments:
        _asset(db, run, segment, asset_type="video_segment", url=f"https://cdn.test/{segment.id}.mp4")
    run.status = "video_segments_approved"
    db.commit()

    async def fail_legacy_submit(*args, **kwargs):
        raise AssertionError("legacy compose submit must not run for real_short_e2e")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.submit_compose", fail_legacy_submit)

    response = client.post(f"/api/video-production/runs/{run.id}/compose")

    assert response.status_code == 200
    assert response.json()["run"]["status"] == "composing"
    jobs = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="episode_compose").all()
    assert len(jobs) == 1
    assert jobs[0].target_id == run.production_episode_id


def test_real_short_compose_defers_video_review_and_compose_preflight_agency_gates_to_worker(db, monkeypatch):
    run, segments = _linked_run_with_segments(db, run_type=REAL_SHORT_E2E, budget_limit=1.0)
    for segment in segments:
        _asset(db, run, segment, asset_type="video_segment", url=f"https://cdn.test/{segment.id}.mp4")
    run.status = "video_segments_approved"
    db.commit()
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("real_short_e2e compose start must not synchronously run agency review")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", fail_if_called)

    response = client.post(f"/api/video-production/runs/{run.id}/compose")

    assert response.status_code == 200
    assert response.json()["run"]["status"] == "composing"
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="episode_compose").count() == 1
