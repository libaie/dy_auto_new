import argparse
import sys

import pytest

from app.db.models import (
    AIModel,
    Episode,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
)
from app.domains.system_configuration.crypto import encrypt
from scripts import smoke_bailian_one_sentence_e2e as smoke


def _seed_expert_model(db, *, provider="bailian", model_name="qwen3.7-plus", api_key="secret-key"):
    model = AIModel(
        name="Expert Model",
        model_type="llm",
        provider=provider,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=encrypt(api_key),
        model_name=model_name,
        enabled=True,
        config_json={
            "scene_key": "llm_agency_expert_review",
            "scene_keys": ["script_generation", "llm_agency_expert_review"],
            "protocol": "openai_chat_completions",
        },
    )
    db.add(model)
    db.commit()
    return model


def _add_segment_scope(db, plan, *, episode_number=1):
    episode = Episode(series_id=plan.series_id, episode_number=episode_number, title=f"Episode {episode_number}")
    db.add(episode)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=episode_number)
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id=f"scene-{episode_number}", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id=f"shot-{episode_number}", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id=f"segment-{episode_number}",
        order_index=1,
        image_prompt="image",
        video_prompt="video",
        reference_roles_json=[],
    )
    db.add(segment)
    db.flush()
    return episode, production_episode, segment


def _scoped_smoke_run(db):
    series = Series(title="Smoke Series", logline="Smoke prompt", genre="drama", total_episodes=1)
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", budget_limit=5.0)
    db.add(plan)
    db.flush()
    episode, production_episode, segment = _add_segment_scope(db, plan)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        status="video_batch_running",
        current_stage="video_rendering",
    )
    db.add(run)
    db.commit()
    return plan, run, segment


def test_parse_args_supports_explicit_expert_gate_bypass(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["smoke", "--prompt", "测试提示词", "--bypass-expert-gates", "--retry-provider-blockers"],
    )

    args = smoke._parse_args()

    assert args.bypass_expert_gates is True
    assert args.retry_provider_blockers is True


def test_paid_smoke_uses_extended_expert_timeout_defaults():
    from app.domains.video_production.one_sentence_video_service import ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS
    from app.domains.video_production.production_worker_service import _deferred_stage_gate_timeout_seconds
    from app.domains.creative_library import reference_asset_service
    assert ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS >= 180
    assert _deferred_stage_gate_timeout_seconds() >= 180
    assert reference_asset_service.REFERENCE_SYNC_POLL_ATTEMPTS >= 180


def test_prepare_expert_gates_default_uses_real_preflight_without_overrides(db, monkeypatch):
    _seed_expert_model(db)
    installed = False

    def fake_install():
        nonlocal installed
        installed = True

    monkeypatch.setattr(smoke, "_install_smoke_gate_overrides", fake_install)

    smoke._prepare_expert_gates(
        db,
        argparse.Namespace(bypass_expert_gates=False),
    )

    assert installed is False


def test_prepare_expert_gates_bypass_installs_overrides_without_preflight(db, monkeypatch):
    installed = False

    def fake_install():
        nonlocal installed
        installed = True

    monkeypatch.setattr(smoke, "_install_smoke_gate_overrides", fake_install)

    smoke._prepare_expert_gates(
        db,
        argparse.Namespace(bypass_expert_gates=True),
    )

    assert installed is True


def test_expert_gate_preflight_requires_bailian_qwen_37_plus(db):
    _seed_expert_model(db, provider="openai-compatible", model_name="qwen3.7-plus")

    with pytest.raises(RuntimeError, match="qwen3.7-plus"):
        smoke._preflight_expert_gate_model(db)


def test_expert_gate_preflight_redacts_api_key_in_log(db, capsys):
    _seed_expert_model(db, api_key="secret-key")

    resolved = smoke._preflight_expert_gate_model(db)
    output = capsys.readouterr().out

    assert resolved["provider"] == "bailian"
    assert resolved["model"] == "qwen3.7-plus"
    assert "secret-key" not in output
    assert "api_key" not in output


def test_pending_reference_generation_is_completed_before_image_stage(db, monkeypatch):
    series = Series(title="Smoke Series", logline="Smoke prompt", genre="drama", total_episodes=1)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Episode 1")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="reference_generation_running",
        current_stage="reference_generation",
        model_trace_json={"one_sentence": {"autostart_images_after_references": True}},
    )
    db.add(run)
    db.commit()
    called = {}

    async def fake_complete_reference_generation(db_arg, run_id, *, autostart_images=None):
        called["run_id"] = run_id
        called["autostart_images"] = autostart_images
        saved = db_arg.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).one()
        saved.status = "image_batch_running"
        saved.current_stage = "image_generation"
        db_arg.commit()
        return saved

    monkeypatch.setattr(
        smoke,
        "complete_one_sentence_reference_generation",
        fake_complete_reference_generation,
    )

    completed = smoke._complete_background_reference_if_pending(db, run.id)

    assert called == {"run_id": run.id, "autostart_images": True}
    assert completed.status == "image_batch_running"


def test_resume_skips_completed_or_later_stage_status(db, monkeypatch):
    series = Series(title="Smoke Series", logline="Smoke prompt", genre="drama", total_episodes=1)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Episode 1")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="video_batch_running",
        current_stage="video_rendering",
    )
    db.add(run)
    db.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("image stage worker should be skipped on video-stage resume")

    monkeypatch.setattr(smoke, "_run_stage_until", fail_if_called)

    smoke._run_stage_unless_done(
        db,
        run.id,
        stage="image_generation",
        done_statuses=smoke.IMAGE_STAGE_DONE_STATUSES,
        lease_prefix="smoke-images",
        batch_size=1,
        max_rounds=1,
    )


def test_paid_smoke_stage_stops_on_provider_billing_block(db, monkeypatch):
    series = Series(title="Smoke Series", logline="Smoke prompt", genre="drama", total_episodes=1)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Episode 1")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", budget_limit=5.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        status="video_batch_running",
        current_stage="video_rendering",
    )
    db.add(run)
    db.commit()

    def fake_worker_step(*args, **kwargs):
        return {
            "lease_id": "smoke-videos-1",
            "processed": 1,
            "remaining": 0,
            "items": [{"ok": False, "status": "retry_wait", "error_code": "PROVIDER_THROTTLED"}],
        }

    monkeypatch.setattr(smoke, "run_real_worker_step", fake_worker_step)

    with pytest.raises(RuntimeError, match="PROVIDER_THROTTLED"):
        smoke._run_stage_until(
            db,
            run.id,
            stage="video_generation",
            done_statuses={"video_review_pending"},
            lease_prefix="smoke-videos",
            batch_size=1,
            max_rounds=3,
        )


def test_paid_smoke_forces_single_worker_batch_for_paid_safety(db, monkeypatch):
    series = Series(title="Smoke Series", logline="Smoke prompt", genre="drama", total_episodes=1)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Episode 1")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", budget_limit=5.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        status="video_batch_running",
        current_stage="video_rendering",
    )
    db.add(run)
    db.commit()
    batch_sizes = []

    def fake_worker_step(*args, **kwargs):
        batch_sizes.append(kwargs["batch_size"])
        return {
            "lease_id": "smoke-videos-1",
            "processed": 1,
            "remaining": 0,
            "items": [{"ok": False, "status": "retry_wait", "error_code": "PROVIDER_THROTTLED"}],
        }

    monkeypatch.setattr(smoke, "run_real_worker_step", fake_worker_step)

    with pytest.raises(RuntimeError, match="PROVIDER_THROTTLED"):
        smoke._run_stage_until(
            db,
            run.id,
            stage="video_generation",
            done_statuses={"video_review_pending"},
            lease_prefix="smoke-videos",
            batch_size=5,
            max_rounds=3,
        )

    assert batch_sizes == [1]


def test_paid_smoke_stage_stops_before_worker_when_prior_provider_block_exists(db, monkeypatch):
    plan, run, segment = _scoped_smoke_run(db)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="video_generation",
        status="retry_wait",
        error_code="PROVIDER_THROTTLED",
        idempotency_key=f"{plan.id}:video_generation:{segment.id}",
    )
    db.add(job)
    db.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("worker must not run while prior provider blocker is recorded")

    monkeypatch.setattr(smoke, "run_real_worker_step", fail_if_called)

    with pytest.raises(RuntimeError, match="existing PROVIDER_THROTTLED"):
        smoke._run_stage_until(
            db,
            run.id,
            stage="video_generation",
            done_statuses={"video_review_pending"},
            lease_prefix="smoke-videos",
            batch_size=1,
            max_rounds=3,
        )


def test_paid_smoke_retry_provider_blockers_explicitly_unblocks_retry_wait_job(db, monkeypatch):
    plan, run, segment = _scoped_smoke_run(db)
    _, _, sibling_segment = _add_segment_scope(db, plan, episode_number=2)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="video_generation",
        status="retry_wait",
        error_code="PROVIDER_THROTTLED",
        error_message="billing blocked",
        idempotency_key=f"{plan.id}:video_generation:{segment.id}:retry",
    )
    sibling_job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=sibling_segment.id,
        stage="video_generation",
        status="retry_wait",
        error_code="PROVIDER_THROTTLED",
        error_message="sibling billing blocked",
        idempotency_key=f"{plan.id}:video_generation:{sibling_segment.id}:retry",
    )
    db.add_all([job, sibling_job])
    db.commit()
    batch_sizes = []

    def fake_worker_step(db_arg, run_id, *, lease_id, batch_size):
        del lease_id
        saved_job = db_arg.query(ProductionJob).filter(ProductionJob.id == job.id).one()
        assert saved_job.error_code is None
        assert saved_job.error_message is None
        saved_job.status = "completed"
        saved_run = db_arg.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).one()
        saved_run.status = "video_review_pending"
        db_arg.commit()
        batch_sizes.append(batch_size)
        return {"lease_id": "smoke-videos-1", "processed": 1, "remaining": 0, "items": [{"ok": True}]}

    monkeypatch.setattr(smoke, "run_real_worker_step", fake_worker_step)

    smoke._run_stage_until(
        db,
        run.id,
        stage="video_generation",
        done_statuses={"video_review_pending"},
        lease_prefix="smoke-videos",
        batch_size=3,
        max_rounds=2,
        retry_provider_blockers=True,
    )

    assert batch_sizes == [1]
    db.refresh(sibling_job)
    assert sibling_job.error_code == "PROVIDER_THROTTLED"
    assert sibling_job.error_message == "sibling billing blocked"
