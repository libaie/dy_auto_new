import pytest

from app.db_models import Episode, ProductionAuditEvent, Series, VideoProductionAsset, VideoProductionRun
from app.services.production_observability import record_production_event
from app.services.video_production_run_types import LEGACY_EPISODE_RUN, MOCK_SERIES_SCALE, REAL_SHORT_E2E


def test_record_production_event_redacts_secret_like_fields(db):
    event = record_production_event(
        db,
        event_type="stage.submitted",
        provider_task_id="task-id",
        payload={
            "password": "password-secret",
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
            "client_secret": "client-secret",
            "secret_key": "secret-key",
            "private_key": "private-key",
            "bearer_token": "bearer-secret",
            "x-api-key": "header-secret",
            "apiKey": "camel-secret",
            "authorization": "Bearer secret",
            "token": "token-secret",
            "api_key": "secret",
            "secret": "generic-secret",
            "nested": {"token": "secret-token", "model": "doubao-seedance-2.0"},
            "items": [
                {"apiKey": "list-camel-secret", "name": "kept"},
                {"headers": {"X-API-KEY": "list-header-secret"}},
            ],
            "provider": "ark",
        },
    )

    saved = db.query(ProductionAuditEvent).filter_by(id=event.id).one()
    assert saved.payload_json["password"] == "[REDACTED]"
    assert saved.payload_json["access_token"] == "[REDACTED]"
    assert saved.payload_json["refresh_token"] == "[REDACTED]"
    assert saved.payload_json["client_secret"] == "[REDACTED]"
    assert saved.payload_json["secret_key"] == "[REDACTED]"
    assert saved.payload_json["private_key"] == "[REDACTED]"
    assert saved.payload_json["bearer_token"] == "[REDACTED]"
    assert saved.payload_json["x-api-key"] == "[REDACTED]"
    assert saved.payload_json["apiKey"] == "[REDACTED]"
    assert saved.payload_json["authorization"] == "[REDACTED]"
    assert saved.payload_json["token"] == "[REDACTED]"
    assert saved.payload_json["api_key"] == "[REDACTED]"
    assert saved.payload_json["secret"] == "[REDACTED]"
    assert saved.payload_json["nested"]["token"] == "[REDACTED]"
    assert saved.payload_json["nested"]["model"] == "doubao-seedance-2.0"
    assert saved.payload_json["items"][0]["apiKey"] == "[REDACTED]"
    assert saved.payload_json["items"][0]["name"] == "kept"
    assert saved.payload_json["items"][1]["headers"]["X-API-KEY"] == "[REDACTED]"
    assert saved.payload_json["provider"] == "ark"


def test_record_production_event_uses_caller_transaction(db):
    event = record_production_event(
        db,
        event_type="run.created",
        payload={"provider": "mock"},
    )
    event_id = event.id

    db.rollback()

    assert db.query(ProductionAuditEvent).filter_by(id=event_id).first() is None


@pytest.mark.asyncio
async def test_image_stage_blocks_when_agency_model_config_missing(db, monkeypatch):
    from app.services.video_production_service import start_image_stage

    series = Series(title="Agency Block", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "duration": 5}]},
    )
    db.add(run)
    db.commit()

    async def fail_submit(*args, **kwargs):
        raise AssertionError("provider stage should not submit without agency config")

    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fail_submit)

    updated = await start_image_stage(db, run.id)

    assert updated.status == "image_human_review_required"
    assert updated.current_stage == "image_review"
    assert updated.pixelle_stage_task_id is None
    assert updated.model_trace_json["agency_reviews"]["image_stage"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    saved_event = db.query(ProductionAuditEvent).filter_by(run_id=run.id, event_type="agency.image_stage.blocked").one()
    assert saved_event.payload_json["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"


def _run(db, *, run_type=REAL_SHORT_E2E):
    series = Series(title="Events", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "image_prompt": "Image prompt",
                "video_prompt": "Video prompt",
                "duration": 5,
            }]
        },
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        run_type=run_type,
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    return run


def _event_payloads(db, run_id):
    return {
        event.event_type: event.payload_json
        for event in db.query(ProductionAuditEvent).filter_by(run_id=run_id).all()
    }


def test_core_run_events_include_run_type(db):
    from app.services.video_production_service import (
        mark_image_stage_assets,
        mark_image_stage_submitted,
        mark_video_stage_assets,
    )

    run = _run(db)

    mark_image_stage_submitted(db, run, "image-task-1", {"model": "test"})
    mark_image_stage_assets(
        db,
        run,
        [{"frame_id": "frame-001", "url": "https://example.test/image.png"}],
        "image-task-1",
    )
    mark_video_stage_assets(
        db,
        run,
        [{"frame_id": "frame-001", "url": "https://example.test/video.mp4"}],
        "video-task-1",
    )

    payloads = _event_payloads(db, run.id)
    for event_type in {
        "image_stage.submitted",
        "image_stage.asset_registered",
        "video_stage.asset_registered",
    }:
        assert payloads[event_type]["run_type"] == REAL_SHORT_E2E


def test_run_type_assigned_event_includes_run_type(db):
    from app.services.video_production_service import create_run_from_episode

    series = Series(title="Assigned", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Image prompt"}]},
    )
    db.add(episode)
    db.commit()

    run = create_run_from_episode(db, series.id, episode.id, run_type=REAL_SHORT_E2E)

    event = db.query(ProductionAuditEvent).filter_by(run_id=run.id, event_type="run_type.assigned").one()
    assert event.payload_json["run_type"] == REAL_SHORT_E2E


@pytest.mark.parametrize(
    ("stage", "scene_key", "event_type"),
    [
        ("image_stage", "image_generation", "provider_config.image_stage.blocked"),
        ("video_stage", "video_rendering", "provider_config.video_stage.blocked"),
        ("compose", "video_composition", "provider_config.compose.blocked"),
    ],
)
def test_provider_config_blocked_events_include_run_type(db, stage, scene_key, event_type):
    from app.services.runtime_model_config import RuntimeModelConfigError
    from app.services.video_production_service import _block_missing_provider_model_config

    run = _run(db)

    _block_missing_provider_model_config(
        db,
        run,
        stage=stage,
        scene_key=scene_key,
        exc=RuntimeModelConfigError("missing config"),
    )

    event = db.query(ProductionAuditEvent).filter_by(run_id=run.id, event_type=event_type).one()
    assert event.payload_json["run_type"] == REAL_SHORT_E2E
    assert event.payload_json["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"


@pytest.mark.asyncio
async def test_video_and_compose_submitted_events_include_run_type(db, monkeypatch):
    from app.services.video_production_service import start_compose_stage, start_video_stage

    run = _run(db, run_type=LEGACY_EPISODE_RUN)
    image = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://example.test/image.png",
        status="approved",
        is_latest=True,
        copy_status="persisted",
        checksum="image-checksum",
        storage_path="output/image.png",
    )
    video = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id="frame-001",
        asset_type="video_segment",
        stage="video_rendering",
        url="https://example.test/video.mp4",
        status="approved",
        is_latest=True,
        copy_status="persisted",
        checksum="video-checksum",
        storage_path="output/video.mp4",
    )
    db.add(image)
    db.commit()

    async def pass_guard(*args, **kwargs):
        return {"stage_status": "approved"}

    async def submit_video(*args, **kwargs):
        return {"stage_task_id": "video-task-1"}

    async def submit_compose(*args, **kwargs):
        return {"stage_task_id": "compose-task-1"}

    def model_config(*args, **kwargs):
        return {"provider": "test", "model": "mock", "api_key": "secret"}

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", pass_guard)
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", submit_video)
    monkeypatch.setattr("app.services.video_production_service.submit_compose", submit_compose)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", model_config)

    run.status = "image_approved"
    db.commit()
    await start_video_stage(db, run.id)

    db.add(video)
    run.status = "video_segments_approved"
    run.current_stage = "video_review"
    db.commit()
    await start_compose_stage(db, run.id)

    payloads = _event_payloads(db, run.id)
    assert payloads["video_stage.submitted"]["run_type"] == LEGACY_EPISODE_RUN
    assert payloads["compose_stage.submitted"]["run_type"] == LEGACY_EPISODE_RUN


def test_final_approval_records_final_video_completed_with_run_type(db):
    from app.services.video_production_service import approve_asset

    run = _run(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url="https://example.test/final.mp4",
        local_path="/tmp/final.mp4",
        status="review_pending",
        is_latest=True,
        copy_status="persisted",
        checksum="final-checksum",
        storage_path="/tmp/final.mp4",
    )
    db.add(asset)
    db.commit()

    approve_asset(db, asset.id, reviewer_user_id="reviewer")

    payloads = _event_payloads(db, run.id)
    assert payloads["run.completed"]["run_type"] == REAL_SHORT_E2E
    assert payloads["final_video.completed"]["run_type"] == REAL_SHORT_E2E
    assert payloads["final_video.completed"]["asset_id"] == asset.id


def test_persist_final_video_records_compose_asset_registered_with_run_type(db):
    from app.services.video_production_service import persist_final_video

    run = _run(db)
    run.pixelle_stage_task_id = "compose-task-1"
    db.commit()

    asset = persist_final_video(
        db,
        run,
        {
            "asset_type": "final_video",
            "url": "https://example.test/final.mp4",
            "local_path": "/tmp/final.mp4",
            "provider_task_id": "provider-final-1",
            "metadata": {"duration": 60},
        },
    )

    event = (
        db.query(ProductionAuditEvent)
        .filter_by(run_id=run.id, event_type="compose_stage.asset_registered")
        .one()
    )
    assert event.provider_task_id == "provider-final-1"
    assert event.payload_json["run_type"] == REAL_SHORT_E2E
    assert event.payload_json["asset_id"] == asset.id
    assert event.payload_json["asset_type"] == "final_video"
    assert event.payload_json["version"] == asset.version


def test_agency_invocation_completed_event_includes_run_type_when_run_exists(db):
    from app.services.agency_persistence import create_or_resume_invocation, finalize_invocation_and_audit

    run = _run(db)
    invocation = create_or_resume_invocation(
        db,
        idempotency_key="task8-run-type-agency",
        series_id=run.series_id,
        episode_id=run.episode_id,
        run_id=run.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        source={
            "repo": "jnMetaCode/agency-agents-zh",
            "commit": "13b8800",
            "path": "specialized/prompt-engineer.md",
            "sha256": "a" * 64,
        },
        input_summary={"frame_count": 1},
    )

    finalize_invocation_and_audit(
        db,
        invocation_id=invocation.id,
        result_status="passed",
        output_summary={"decision": "pass"},
        evidence=[],
    )

    event = (
        db.query(ProductionAuditEvent)
        .filter_by(run_id=run.id, event_type="agency.invocation.completed")
        .one()
    )
    assert event.payload_json["agency_invocation_id"] == invocation.id
    assert event.payload_json["run_type"] == REAL_SHORT_E2E


def test_mock_scheduler_step_completed_records_provider_free_evidence(db):
    from app.services.mock_scale_scheduler_service import advance_mock_scheduler, create_mock_scale_run

    result = create_mock_scale_run(
        db,
        prompt="A mock provider-free series.",
        title="Mock Events",
        target_duration_seconds=3 * 60,
    )
    run = result["run"]

    advance_mock_scheduler(db, run.id, limit=2)

    event = (
        db.query(ProductionAuditEvent)
        .filter_by(run_id=run.id, event_type="mock_scheduler.step_completed")
        .one()
    )
    assert event.payload_json["run_type"] == MOCK_SERIES_SCALE
    assert event.payload_json["provider_calls"] == 0
    assert event.payload_json["completed"] is False
    assert event.payload_json["remaining"] == 1
    assert event.payload_json["open_jobs"] == 1
    assert len(event.payload_json["job_ids"]) == 2


def test_mock_scale_run_records_run_type_assigned_event(db):
    from app.services.mock_scale_scheduler_service import create_mock_scale_run

    result = create_mock_scale_run(
        db,
        prompt="A mock provider-free series.",
        title="Mock Assigned",
        target_duration_seconds=3 * 60,
    )
    run = result["run"]

    event = (
        db.query(ProductionAuditEvent)
        .filter_by(run_id=run.id, event_type="run_type.assigned")
        .one()
    )
    assert event.production_plan_id == run.production_plan_id
    assert event.production_episode_id == run.production_episode_id
    assert event.payload_json["run_type"] == MOCK_SERIES_SCALE
    assert event.payload_json["source"] == MOCK_SERIES_SCALE
