from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import bj_now
from app.db.models import (
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
)
from app.main import app
from app.domains.video_production.production_action_result import ProductionActionResult
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E

client = TestClient(app)


def _run_with_jobs(db, *, job_count=3, run_type=REAL_SHORT_E2E):
    series = Series(title="Worker", logline="Worker", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, budget_limit=5.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=run_type,
        production_plan_id=plan.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    for index in range(job_count):
        db.add(ProductionJob(
            plan_id=plan.id,
            target_type="production_segment",
            target_id=f"seg-{index + 1}",
            stage="image_generation",
            status="queued",
            idempotency_key=f"{run.id}:seg-{index + 1}:image:v1",
            priority=index,
            scheduled_at=bj_now(),
        ))
    db.commit()
    return run


def _linked_run_with_image_job(db):
    return _linked_run_with_image_job_refs(db, reference_roles_json=[
        {"role": "character_anchor", "url": "https://cdn.test/character-anchor.png", "priority": 1},
        {"role": "style_anchor", "url": "https://cdn.test/style-anchor.png", "priority": 2},
    ])


def _linked_run_with_image_job_refs(db, *, reference_roles_json):
    series = Series(title="Worker Real", logline="Worker Real", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, budget_limit=5.0)
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready")
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready", duration_seconds=6)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-01",
        order_index=1,
        status="planned",
        duration_seconds=6,
        image_prompt="neon courier",
        video_prompt="slow push",
        reference_roles_json=reference_roles_json,
    )
    db.add(segment)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=REAL_SHORT_E2E,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
        status="image_batch_running",
        current_stage="image_generation",
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
        scheduled_at=bj_now(),
    )
    db.add(job)
    db.commit()
    return run, segment


def test_real_worker_step_claims_limited_batch_and_returns_visible_summary(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run = _run_with_jobs(db, job_count=3)

    async def fake_execute_job(db, run, job):
        job.status = "completed"
        db.commit()
        return {"job_id": job.id, "status": job.status}

    monkeypatch.setattr("app.domains.video_production.production_worker_service.execute_real_job", fake_execute_job)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=2)

    assert result["ok"] is True
    assert result["processed"] == 2
    assert result["remaining"] == 1
    assert len(result["items"]) == 2
    assert {item["ok"] for item in result["items"]} == {True}
    assert all(item["job_id"] for item in result["items"])
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, status="queued").count() == 1


def test_real_worker_step_route_accepts_background_mode(db, monkeypatch):
    run = _run_with_jobs(db, job_count=1)
    calls = []

    def fake_run_real_worker_step(db, run_id, *, lease_id, batch_size):
        calls.append({"run_id": run_id, "lease_id": lease_id, "batch_size": batch_size})
        return {"ok": True, "processed": batch_size}

    monkeypatch.setattr("app.domains.video_production.production_worker_service.run_real_worker_step", fake_run_real_worker_step)

    resp = client.post(f"/api/video-production/runs/{run.id}/worker-step", json={
        "lease_id": "background-test",
        "batch_size": 1,
        "async_mode": True,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["run_id"] == run.id
    assert calls == [{"run_id": run.id, "lease_id": "background-test", "batch_size": 1}]


def test_real_worker_step_does_not_process_more_than_batch_size_and_reports_remaining(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run = _run_with_jobs(db, job_count=5)
    processed = []

    async def fake_execute_job(db, run, job):
        processed.append(job.id)
        job.status = "completed"
        db.commit()
        return {"job_id": job.id, "status": job.status}

    monkeypatch.setattr("app.domains.video_production.production_worker_service.execute_real_job", fake_execute_job)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=2)

    assert len(processed) == 2
    assert result["processed"] == 2
    assert result["remaining"] == 3


@pytest.mark.parametrize(
    ("stage", "approved_status", "approved_stage"),
    [
        ("image_generation", "image_approved", "image_review"),
        ("video_generation", "video_segments_approved", "video_review"),
        ("video_composition", "completed", "completed"),
    ],
)
def test_worker_status_sync_does_not_downgrade_autopilot_approved_gate(db, stage, approved_status, approved_stage):
    from app.domains.video_production.production_worker_service import _update_run_status_after_stage_job

    run = _run_with_jobs(db, job_count=0)
    run.status = approved_status
    run.current_stage = approved_stage
    run.model_trace_json = {"autopilot": {"enabled": True, "source": "one_sentence"}}
    db.commit()

    _update_run_status_after_stage_job(db, run, stage)

    db.refresh(run)
    assert run.status == approved_status
    assert run.current_stage == approved_stage


def test_real_worker_step_records_repairable_failure_and_continues(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run = _run_with_jobs(db, job_count=2)
    calls = {"count": 0}

    async def fake_execute_job(db, run, job):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ProductionRepairableError(
                code=ProductionErrorCode.PROVIDER_THROTTLED,
                message="Provider throttle reached.",
                repair_action="Retry later.",
                repair_route=f"/video-production/{run.id}",
                retryable=True,
                affected_ids=[job.id],
                cause="provider_stage_throttled",
            )
        job.status = "completed"
        db.commit()
        return {"job_id": job.id, "status": job.status}

    monkeypatch.setattr("app.domains.video_production.production_worker_service.execute_real_job", fake_execute_job)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=2)

    assert result["processed"] == 2
    assert result["items"][0]["ok"] is False
    assert result["items"][0]["error_code"] == "PROVIDER_THROTTLED"
    assert result["items"][1]["ok"] is True

    failed_job = db.query(ProductionJob).filter_by(error_code="PROVIDER_THROTTLED").one()
    assert failed_job.status == "retry_wait"
    assert failed_job.retryable is True
    assert failed_job.attempt_count == 0
    assert failed_job.retry_after is not None
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, status="completed").count() == 1


def test_real_worker_step_sync_required_does_not_consume_attempt(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run = _run_with_jobs(db, job_count=1)

    async def fake_execute_job(db, run, job):
        return ProductionActionResult.blocked(
            ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED,
            "Provider stage task still requires sync.",
            "Run provider task sync after the provider finishes the task.",
            repair_route=f"/video-production/{run.id}",
            affected_ids=[job.id],
            retryable=True,
        )

    monkeypatch.setattr("app.domains.video_production.production_worker_service.execute_real_job", fake_execute_job)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    assert result["processed"] == 1
    assert result["items"][0]["ok"] is False
    assert result["items"][0]["status"] == "retry_wait"
    assert result["items"][0]["attempt_count"] == 0
    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
    assert job.status == "retry_wait"
    assert job.attempt_count == 0
    assert job.retry_after is not None
    assert job.lease_id is None


def test_real_worker_step_terminal_provider_failure_is_not_resynced(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run, segment = _linked_run_with_image_job(db)
    calls = {"sync": 0}

    def fake_config(db, scene_key):
        return {
            "provider": "pixelle",
            "model": scene_key,
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

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        return {"ok": True, "stage_task_id": "terminal-provider-task"}

    async def fake_get_stage_task(db, stage_task_id):
        calls["sync"] += 1
        assert stage_task_id == "terminal-provider-task"
        return {"ok": False, "status": "failed", "error": "provider stopped"}

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    monkeypatch.setattr("app.domains.video_production.production_worker_service.resolve_runtime_model_config", fake_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.get_stage_task", fake_get_stage_task)

    first = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    assert first["processed"] == 1
    assert first["items"][0]["ok"] is False
    assert first["items"][0]["status"] == "failed"
    assert first["items"][0]["retryable"] is False
    assert calls["sync"] == 1

    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
    assert job.target_id == segment.id
    assert job.status == "failed"
    assert job.retryable is False
    assert job.provider_task_id is None
    db.refresh(run)
    assert run.status == "failed"

    second = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    assert second["processed"] == 0
    assert calls["sync"] == 1


@pytest.mark.parametrize("raised", [ValueError("bad worker payload"), RuntimeError("provider exploded")])
def test_real_worker_step_captures_job_exceptions_and_clears_lease(db, monkeypatch, raised):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run = _run_with_jobs(db, job_count=1)

    async def fake_execute_job(db, run, job):
        raise raised

    monkeypatch.setattr("app.domains.video_production.production_worker_service.execute_real_job", fake_execute_job)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    assert result["processed"] == 1
    assert result["items"][0]["ok"] is False
    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
    assert job.status in {"failed", "retry_wait"}
    assert job.lease_id is None
    assert job.leased_until is None
    assert job.attempt_count == 1


def test_real_worker_step_executes_image_job_and_persists_asset(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run, segment = _linked_run_with_image_job(db)
    submitted = {}

    def fake_config(db, scene_key):
        return {
            "provider": "pixelle",
            "model": scene_key,
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

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        submitted["frames"] = frames
        submitted["template_config"] = template_config
        return {"ok": True, "stage_task_id": "image-task-1"}

    async def fake_get_stage_task(db, stage_task_id):
        assert stage_task_id == "image-task-1"
        frame = submitted["frames"][0]
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": frame["production_segment_id"],
                "production_segment_id": frame["production_segment_id"],
                "url": "https://cdn.test/image.png",
                "source_url": "https://cdn.test/image.png",
                "storage_path": "output/image.png",
                "checksum": "sha256-image",
                "copy_status": "persisted",
                "metadata": {"duration": frame["duration"]},
            }],
            "usage": {"cost": 0.01, "units": {"images": 1}},
        }

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    monkeypatch.setattr("app.domains.video_production.production_worker_service.resolve_runtime_model_config", fake_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.domains.video_production.production_worker_service.run_ai_audit_for_assets", lambda db, run, assets: assets)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    assert result["processed"] == 1
    assert result["items"][0]["ok"] is True
    assert submitted["frames"][0]["production_segment_id"] == segment.id
    assert submitted["template_config"]["external_task_id"]
    assert submitted["template_config"]["provider_stage_task_id"] == submitted["template_config"]["external_task_id"]

    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
    assert job.status == "completed"
    asset = db.query(VideoProductionAsset).filter_by(run_id=run.id, asset_type="image").one()
    assert asset.production_segment_id == segment.id
    assert asset.copy_status == "persisted"
    assert asset.checksum == "sha256-image"
    assert asset.provider_stage_task_id


def test_real_worker_step_blocks_image_job_without_reference_urls_before_provider(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run, segment = _linked_run_with_image_job_refs(db, reference_roles_json=[])

    def fake_config(db, scene_key):
        return {
            "provider": "pixelle",
            "model": scene_key,
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

    async def fail_submit_image_batch(*args, **kwargs):
        raise AssertionError("worker submitted a paid image task without reference URLs")

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    monkeypatch.setattr("app.domains.video_production.production_worker_service.resolve_runtime_model_config", fake_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fail_submit_image_batch)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    assert result["processed"] == 1
    assert result["items"][0]["ok"] is False
    assert result["items"][0]["error_code"] == ProductionErrorCode.REVIEW_GATE_BLOCKED.value
    assert segment.id in result["items"][0]["repair"]["affected_ids"]
    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
    assert job.status == "failed"


def test_real_worker_step_persists_registered_provider_asset_before_audit(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run, segment = _linked_run_with_image_job(db)
    submitted = {}
    persisted_ids = []
    audited_ids = []

    def fake_config(db, scene_key):
        return {
            "provider": "pixelle",
            "model": scene_key,
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

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        submitted["frames"] = frames
        return {"ok": True, "stage_task_id": "image-task-registered"}

    async def fake_get_stage_task(db, stage_task_id):
        frame = submitted["frames"][0]
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": frame["production_segment_id"],
                "production_segment_id": frame["production_segment_id"],
                "url": "https://cdn.test/image.png",
                "source_url": "https://cdn.test/image.png",
                "metadata": {"duration": frame["duration"]},
            }],
            "usage": {"cost": 0.01, "units": {"images": 1}},
        }

    def fake_persist_provider_asset(db, asset_id, *, output_root, pixelle_output_root=None):
        del output_root, pixelle_output_root
        asset = db.query(VideoProductionAsset).filter_by(id=asset_id).one()
        persisted_ids.append(asset.id)
        asset.storage_path = f"output/video-production/{asset.id}.png"
        asset.local_path = asset.storage_path
        asset.checksum = "sha256-persisted"
        asset.copy_status = "persisted"
        asset.status = "review_pending"
        db.commit()
        db.refresh(asset)
        return asset

    def fake_audit(db, run, assets):
        audited_ids.extend(asset.id for asset in assets)
        assert all(asset.copy_status == "persisted" for asset in assets)
        return assets

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    monkeypatch.setattr("app.domains.video_production.production_worker_service.resolve_runtime_model_config", fake_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.domains.video_production.asset_storage_guard.persist_provider_asset", fake_persist_provider_asset)
    monkeypatch.setattr("app.domains.video_production.production_worker_service.run_ai_audit_for_assets", fake_audit)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    assert result["processed"] == 1
    asset = db.query(VideoProductionAsset).filter_by(run_id=run.id, asset_type="image").one()
    assert asset.production_segment_id == segment.id
    assert asset.copy_status == "persisted"
    assert asset.checksum == "sha256-persisted"
    assert persisted_ids == [asset.id]
    assert audited_ids == [asset.id]


def test_real_worker_keeps_run_running_until_stage_jobs_are_finished(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run, first_segment = _linked_run_with_image_job(db)
    shot = db.query(ProductionShot).one()
    second_segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-02",
        order_index=2,
        status="planned",
        duration_seconds=6,
        image_prompt="neon courier second beat",
        video_prompt="slow push continued",
        reference_roles_json=[
            {"role": "character_anchor", "url": "https://cdn.test/character-anchor-2.png", "priority": 1},
            {"role": "style_anchor", "url": "https://cdn.test/style-anchor-2.png", "priority": 2},
        ],
    )
    db.add(second_segment)
    db.flush()
    db.add(ProductionJob(
        plan_id=run.production_plan_id,
        target_type="production_segment",
        target_id=second_segment.id,
        stage="image_generation",
        status="queued",
        idempotency_key=f"{run.id}:{second_segment.id}:image_generation:v1",
        scheduled_at=bj_now(),
    ))
    db.commit()

    submitted_targets = []

    def fake_config(db, scene_key):
        return {
            "provider": "pixelle",
            "model": scene_key,
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

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        frame = frames[0]
        submitted_targets.append(frame["production_segment_id"])
        return {"ok": True, "stage_task_id": f"image-task-{len(submitted_targets)}"}

    async def fake_get_stage_task(db, stage_task_id):
        target_id = submitted_targets[-1]
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": target_id,
                "production_segment_id": target_id,
                "url": f"https://cdn.test/{target_id}.png",
                "source_url": f"https://cdn.test/{target_id}.png",
                "storage_path": f"output/{target_id}.png",
                "checksum": f"sha256-{target_id}",
                "copy_status": "persisted",
                "metadata": {"duration": 6},
            }],
            "usage": {"cost": 0.01, "units": {"images": 1}},
        }

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    monkeypatch.setattr("app.domains.video_production.production_worker_service.resolve_runtime_model_config", fake_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.domains.video_production.production_worker_service.run_ai_audit_for_assets", lambda db, run, assets: assets)

    first = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)
    db.refresh(run)

    assert first["processed"] == 1
    assert run.status == "image_batch_running"
    assert set(submitted_targets) == {first_segment.id}

    second = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)
    db.refresh(run)

    assert second["processed"] == 1
    assert run.status == "image_review_pending"
    assert set(submitted_targets) == {first_segment.id, second_segment.id}


def test_compose_worker_persists_final_asset_before_final_audit(db, monkeypatch, tmp_path):
    from app.domains.video_production import production_worker_service
    pixelle_config = tmp_path / "Pixelle-Video" / "config.yaml"
    monkeypatch.setattr(production_worker_service, "PIXELLE_CONFIG_PATH", str(pixelle_config))
    run = _run_with_jobs(db, job_count=0)
    job = ProductionJob(
        plan_id=run.production_plan_id,
        target_type="production_episode",
        target_id=run.production_episode_id or run.id,
        stage="episode_compose",
        status="leased",
        lease_id="worker-a",
        idempotency_key=f"{run.id}:compose:v1",
        scheduled_at=bj_now(),
    )
    db.add(job)
    db.commit()
    audited = []

    def fake_persist_provider_asset(db, asset_id, *, output_root, pixelle_output_root=None):
        del output_root
        assert Path(pixelle_output_root) == pixelle_config.parent / "output"
        asset = db.query(VideoProductionAsset).filter_by(id=asset_id).one()
        asset.storage_path = f"output/video-production/{asset.id}.mp4"
        asset.local_path = asset.storage_path
        asset.checksum = "sha256-final"
        asset.copy_status = "persisted"
        asset.status = "review_pending"
        db.commit()
        db.refresh(asset)
        return asset

    def fake_final_audit(db, run, asset):
        assert asset.copy_status == "persisted"
        assert asset.checksum == "sha256-final"
        assert asset.storage_path
        audited.append(asset.id)
        return asset

    monkeypatch.setattr("app.domains.video_production.asset_storage_guard.persist_provider_asset", fake_persist_provider_asset)
    monkeypatch.setattr("app.domains.video_production.video_production_service.run_final_audit_for_asset", fake_final_audit)

    result = ProductionActionResult.success(data={
        "provider_result": {
            "provider_task_id": "compose-task-1",
            "assets": [{
                "asset_type": "final_video",
                "url": "https://cdn.test/final.mp4",
                "source_url": "https://cdn.test/final.mp4",
                "metadata": {"duration": 8},
            }],
        }
    })

    production_worker_service._persist_completed_provider_result(db, run, job, result)

    asset = db.query(VideoProductionAsset).filter_by(run_id=run.id, asset_type="final_video").one()
    assert asset.copy_status == "persisted"
    assert audited == [asset.id]


def test_real_worker_marks_completed_provider_result_without_assets_failed(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run, _segment = _linked_run_with_image_job(db)

    def fake_config(db, scene_key):
        return {
            "provider": "seedance",
            "model_name": "seedream",
            "config": {
                "real_paid_allowed": True,
                "supports_external_task_id": True,
                "supports_task_query": True,
                "returns_asset_url": True,
                "returns_usage": True,
                "estimated_cost": 0.01,
                "supports_text_to_image": True,
            },
        }

    async def fake_submit_image_batch(**kwargs):
        return {"ok": True, "stage_task_id": "image-task-empty"}

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [],
            "usage": {"cost": 0.01, "units": {"images": 0}},
        }

    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    monkeypatch.setattr("app.domains.video_production.production_worker_service.resolve_runtime_model_config", fake_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.get_stage_task", fake_get_stage_task)

    result = run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    item = result["items"][0]
    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
    db.refresh(run)
    assert item["ok"] is False
    assert item["error_code"] == ProductionErrorCode.PROVIDER_TASK_FAILED.value
    assert "no assets" in item["error"].lower()
    assert job.status == "failed"
    assert run.status == "failed"
    assert db.query(VideoProductionAsset).filter_by(run_id=run.id).count() == 0


def test_real_worker_step_does_not_process_mock_series_scale_runs(db, monkeypatch):
    from app.domains.video_production.production_worker_service import run_real_worker_step

    run = _run_with_jobs(db, job_count=1, run_type=MOCK_SERIES_SCALE)

    async def fail_execute_job(*args, **kwargs):
        raise AssertionError("mock_series_scale jobs must not be processed by real worker step")

    monkeypatch.setattr("app.domains.video_production.production_worker_service.execute_real_job", fail_execute_job)

    with pytest.raises(ProductionRepairableError) as exc:
        run_real_worker_step(db, run.id, lease_id="worker-a", batch_size=1)

    assert exc.value.code == ProductionErrorCode.INVALID_RUN_TYPE


def test_real_worker_step_route_maps_repairable_errors_to_409(db):
    run = _run_with_jobs(db, job_count=1, run_type=MOCK_SERIES_SCALE)

    response = client.post(
        f"/api/video-production/runs/{run.id}/worker-step",
        json={"lease_id": "worker-a", "batch_size": 1},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_RUN_TYPE"


def test_real_worker_step_route_maps_only_missing_run_value_error_to_404(db):
    response = client.post(
        "/api/video-production/runs/missing-run/worker-step",
        json={"lease_id": "worker-a", "batch_size": 1},
    )

    assert response.status_code == 404


def test_real_worker_step_route_maps_non_missing_run_value_error_to_409(db):
    run = _run_with_jobs(db, job_count=1)
    run.production_plan_id = None
    db.commit()

    response = client.post(
        f"/api/video-production/runs/{run.id}/worker-step",
        json={"lease_id": "worker-a", "batch_size": 1},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "RUN_LINK_MISSING"
