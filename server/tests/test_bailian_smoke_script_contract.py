import argparse
import sys

import pytest

from app.db_models import AIModel
from app.services.crypto import encrypt
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
