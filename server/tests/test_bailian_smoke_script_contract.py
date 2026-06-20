import argparse
import sys

import pytest

from app.db.models import AIModel, Episode, Series, VideoProductionRun
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


def test_parse_args_supports_explicit_expert_gate_bypass(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["smoke", "--prompt", "测试提示词", "--bypass-expert-gates"],
    )

    args = smoke._parse_args()

    assert args.bypass_expert_gates is True


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
