import pytest

from app.db_models import Episode, ProductionAuditEvent, Series, VideoProductionAsset, VideoProductionRun
from app.services.video_production_service import VideoProductionError, start_image_stage, start_video_stage


def _storyboard_run(db):
    series = Series(title="Provider Config", logline="Test", genre="drama")
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
    return run, episode


async def _agency_pass(*args, **kwargs):
    return {"stage_status": "passed", "invocation_ids": ["agency-ok"], "invocations": []}


@pytest.mark.asyncio
async def test_image_stage_blocks_when_provider_model_config_missing_after_agency_pass(db, monkeypatch):
    run, _episode = _storyboard_run(db)

    async def fail_submit(*args, **kwargs):
        raise AssertionError("image provider should not submit without runtime config")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fail_submit)

    with pytest.raises(VideoProductionError, match="image_generation"):
        await start_image_stage(db, run.id)

    db.refresh(run)
    assert run.status == "image_human_review_required"
    assert run.current_stage == "image_review"
    assert run.pixelle_stage_task_id is None
    error = run.model_trace_json["provider_model_config_errors"]["image_generation"]
    assert error["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"
    saved_event = db.query(ProductionAuditEvent).filter_by(
        run_id=run.id,
        event_type="provider_config.image_stage.blocked",
    ).one()
    assert saved_event.payload_json["scene_key"] == "image_generation"
    assert saved_event.payload_json["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"


@pytest.mark.asyncio
async def test_video_stage_blocks_when_provider_model_config_missing_after_agency_pass(db, monkeypatch):
    run, episode = _storyboard_run(db)
    run.status = "image_approved"
    run.current_stage = "image_review"
    db.add(VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/image.png",
        version=1,
        status="approved",
        copy_status="persisted",
        checksum="image-checksum",
        storage_path="output/image.png",
    ))
    db.commit()

    async def fail_submit(*args, **kwargs):
        raise AssertionError("video provider should not submit without runtime config")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fail_submit)

    with pytest.raises(VideoProductionError, match="video_rendering"):
        await start_video_stage(db, run.id)

    db.refresh(run)
    assert run.status == "video_human_review_required"
    assert run.current_stage == "video_review"
    assert run.pixelle_stage_task_id is None
    error = run.model_trace_json["provider_model_config_errors"]["video_rendering"]
    assert error["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"
    saved_event = db.query(ProductionAuditEvent).filter_by(
        run_id=run.id,
        event_type="provider_config.video_stage.blocked",
    ).one()
    assert saved_event.payload_json["scene_key"] == "video_rendering"
    assert saved_event.payload_json["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"
