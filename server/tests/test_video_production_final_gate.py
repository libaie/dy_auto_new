import pytest

from app.db.models import Episode, GeneratedVideo, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.video_production.video_production_service import (
    VideoProductionError,
    approve_asset,
    complete_final_video,
    reject_asset,
    run_final_audit_for_asset,
    sync_compose_stage_results,
)


def _run_ready_for_final(db):
    series = Series(title="Final Gate", logline="Test", genre="drama", target_duration=60)
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
        status="composing",
        current_stage="composition",
        pixelle_stage_task_id="compose-task-1",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    return run, episode


def _final_asset(db, run, episode, *, status="review_pending", is_latest=True):
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url="https://cdn.test/final.mp4",
        local_path="output/final.mp4",
        duration_seconds=5,
        version=1,
        status=status,
        pixelle_task_id="compose-task-1",
        is_latest=is_latest,
        copy_status="persisted",
        checksum="final-checksum",
        storage_path="output/final.mp4",
    )
    db.add(asset)
    db.commit()
    return asset


def _versioned_final_asset(db, run, episode, *, version, status="review_pending", is_latest=True):
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url=f"https://cdn.test/final-v{version}.mp4",
        local_path=f"output/final-v{version}.mp4",
        duration_seconds=5,
        version=version,
        status=status,
        pixelle_task_id=f"compose-task-{version}",
        is_latest=is_latest,
    )
    db.add(asset)
    db.commit()
    return asset


@pytest.mark.asyncio
async def test_sync_compose_results_registers_final_asset_without_writeback(db, monkeypatch):
    run, episode = _run_ready_for_final(db)

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": "final",
                "asset_type": "final_video",
                "url": "https://cdn.test/final.mp4",
                "local_path": "output/final.mp4",
                "storage_path": "output/final.mp4",
                "checksum": "final-checksum",
                "copy_status": "persisted",
                "metadata": {"duration": 5},
            }],
        }

    monkeypatch.setattr("app.domains.video_production.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr(
        "app.domains.video_production.video_production_service.resolve_runtime_model_config",
        lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"},
    )
    monkeypatch.setattr(
        "app.domains.quality_audit.audit_router._do_audit",
        lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []},
    )

    asset = await sync_compose_stage_results(db, run.id)

    assert asset.asset_type == "final_video"
    assert asset.status == "review_pending"
    assert asset.is_latest is True
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "final_review_pending"
    assert run.current_stage == "final_review"
    assert episode.status == "pending"
    assert episode.video_url is None
    assert episode.duration_seconds is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_human_approve_final_asset_writes_back_and_completes_run(db):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = _final_asset(db, run, episode)

    approved = approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="approved")

    assert approved.status == "approved"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "completed"
    assert run.current_stage == "completed"
    assert episode.status == "done"
    assert episode.video_url == "output/final.mp4"
    assert episode.duration_seconds == 5
    saved = db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).one()
    assert saved.video_path == "output/final.mp4"
    assert saved.status == "completed"


def test_complete_final_video_requires_human_approval_record(db):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = _final_asset(db, run, episode, status="approved")

    with pytest.raises(ProductionRepairableError) as exc_info:
        complete_final_video(db, run, asset)

    assert exc_info.value.code == ProductionErrorCode.REVIEW_GATE_BLOCKED
    assert exc_info.value.cause == "final_human_approval_missing"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "final_review_pending"
    assert run.current_stage == "final_review"
    assert episode.status == "pending"
    assert episode.video_url is None
    assert episode.duration_seconds is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_reject_final_asset_does_not_write_back(db):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = _final_asset(db, run, episode)

    rejected = reject_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="bad cut")

    assert rejected.status == "rejected"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "video_segments_approved"
    assert run.current_stage == "video_review"
    assert episode.status == "pending"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_ai_audit_approval_does_not_complete_final_writeback(db, monkeypatch):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = _final_asset(db, run, episode)
    monkeypatch.setattr(
        "app.domains.video_production.video_production_service.resolve_runtime_model_config",
        lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"},
    )
    monkeypatch.setattr(
        "app.domains.quality_audit.audit_router._do_audit",
        lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []},
    )

    audited = run_final_audit_for_asset(db, run, asset)

    assert audited.status == "review_pending"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "final_review_pending"
    assert run.current_stage == "final_review"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_final_audit_records_runtime_model_name(db, monkeypatch):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = _final_asset(db, run, episode)
    monkeypatch.setattr(
        "app.domains.video_production.video_production_service.resolve_runtime_model_config",
        lambda db, scene: {"provider": "bailian", "api_key": "x", "model": "qwen3.7-plus"},
    )
    monkeypatch.setattr(
        "app.domains.quality_audit.audit_router._do_audit",
        lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []},
    )

    run_final_audit_for_asset(db, run, asset)

    review = db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="ai").one()
    assert review.model_trace_json["auditor_model"] == "bailian"
    assert review.model_trace_json["auditor_model_name"] == "qwen3.7-plus"


def test_autopilot_final_audit_still_requires_human_approval(db, monkeypatch):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    run.model_trace_json = {"autopilot": {"enabled": True, "source": "test"}}
    asset = _final_asset(db, run, episode)
    monkeypatch.setattr(
        "app.domains.video_production.video_production_service.resolve_runtime_model_config",
        lambda db, scene: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )

    audited = run_final_audit_for_asset(db, run, asset)

    assert audited.status == "review_pending"
    db.refresh(run)
    db.refresh(episode)
    assert db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="auto").count() == 0
    assert run.status == "final_review_pending"
    assert run.current_stage == "final_review"
    assert episode.status == "pending"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_human_approve_final_asset_requires_latest_final_gate(db):
    run, episode = _run_ready_for_final(db)
    run.status = "video_segments_approved"
    run.current_stage = "video_review"
    asset = _final_asset(db, run, episode)

    with pytest.raises(VideoProductionError, match="final review"):
        approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="too early")


def test_human_approve_old_final_asset_requires_latest_asset(db, monkeypatch):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    old_asset = _versioned_final_asset(db, run, episode, version=1, is_latest=False)
    latest_asset = _versioned_final_asset(db, run, episode, version=2, is_latest=True)

    def fail_complete(*args, **kwargs):
        raise AssertionError("complete_final_video must not be called for stale final assets")

    monkeypatch.setattr("app.domains.video_production.video_production_service.complete_final_video", fail_complete)

    with pytest.raises(ProductionRepairableError) as exc_info:
        approve_asset(db, old_asset.id, reviewer_user_id="reviewer-1", comment="old")
    assert exc_info.value.code == ProductionErrorCode.STALE_ASSET_VERSION

    assert db.query(VideoReviewRecord).filter_by(asset_id=old_asset.id, review_type="human").count() == 0
    db.refresh(old_asset)
    db.refresh(latest_asset)
    db.refresh(episode)
    assert old_asset.status == "review_pending"
    assert latest_asset.status == "review_pending"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_human_reject_old_final_asset_requires_latest_asset(db):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    old_asset = _versioned_final_asset(db, run, episode, version=1, is_latest=False)
    latest_asset = _versioned_final_asset(db, run, episode, version=2, is_latest=True)

    with pytest.raises(ProductionRepairableError) as exc_info:
        reject_asset(db, old_asset.id, reviewer_user_id="reviewer-1", comment="old")
    assert exc_info.value.code == ProductionErrorCode.STALE_ASSET_VERSION

    assert db.query(VideoReviewRecord).filter_by(asset_id=old_asset.id, review_type="human").count() == 0
    db.refresh(old_asset)
    db.refresh(latest_asset)
    db.refresh(run)
    db.refresh(episode)
    assert old_asset.status == "review_pending"
    assert latest_asset.status == "review_pending"
    assert run.status == "final_review_pending"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_human_approve_final_asset_requires_review_pending_status(db, monkeypatch):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = _final_asset(db, run, episode, status="approved")

    def fail_complete(*args, **kwargs):
        raise AssertionError("complete_final_video must not be called for non-pending assets")

    monkeypatch.setattr("app.domains.video_production.video_production_service.complete_final_video", fail_complete)

    with pytest.raises(VideoProductionError, match="review_pending"):
        approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="approve again")

    db.refresh(asset)
    db.refresh(run)
    db.refresh(episode)
    assert asset.status == "approved"
    assert run.status == "final_review_pending"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


@pytest.mark.parametrize("status", ["rejected", "failed"])
def test_human_approve_final_asset_rejects_terminal_or_failed_statuses(db, status):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = _final_asset(db, run, episode, status=status)

    with pytest.raises(VideoProductionError, match="review_pending"):
        approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="bad state")

    db.refresh(asset)
    db.refresh(episode)
    assert asset.status == status
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


@pytest.mark.parametrize("status", ["approved", "rejected", "failed"])
def test_human_reject_final_asset_requires_review_pending_status(db, status):
    run, episode = _run_ready_for_final(db)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset = _final_asset(db, run, episode, status=status)

    with pytest.raises(VideoProductionError, match="review_pending"):
        reject_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="bad state")

    db.refresh(asset)
    db.refresh(run)
    assert asset.status == status
    assert run.status == "final_review_pending"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0
