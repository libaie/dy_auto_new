import pytest

from app.domains.agency_operations.agency_runtime_contracts import AgencyRuntimeError
from app.domains.ai_video_series.langchain_runtime.models import (
    build_langchain_openai_kwargs,
    ensure_langchain_provider_supported,
)


def _runtime_config(**overrides):
    config = {
        "provider": "bailian",
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-test",
        "config": {"temperature": 0.2, "max_tokens": 4096, "timeout": 90},
    }
    config.update(overrides)
    return config


def test_build_langchain_openai_kwargs_preserves_runtime_model_config():
    kwargs = build_langchain_openai_kwargs(_runtime_config())

    assert kwargs == {
        "model": "qwen-plus",
        "api_key": "sk-test",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "temperature": 0.2,
        "max_tokens": 4096,
        "timeout": 90.0,
    }


def test_build_langchain_openai_kwargs_accepts_model_id_fallback():
    kwargs = build_langchain_openai_kwargs(_runtime_config(model="", model_id="qwen-max"))

    assert kwargs["model"] == "qwen-max"


@pytest.mark.parametrize("provider", ["openai", "ark", "doubao", "openai-compatible", "bailian"])
def test_langchain_provider_allows_existing_openai_compatible_providers(provider):
    ensure_langchain_provider_supported(_runtime_config(provider=provider))


def test_langchain_provider_allows_explicit_chat_completions_protocol():
    ensure_langchain_provider_supported(
        _runtime_config(provider="custom", config={"protocol": "openai_chat_completions"})
    )


def test_langchain_provider_rejects_unsupported_provider():
    with pytest.raises(AgencyRuntimeError) as exc:
        ensure_langchain_provider_supported(_runtime_config(provider="anthropic"))

    assert exc.value.error_code == "EXPERT_MODEL_PROVIDER_UNSUPPORTED"


def test_build_langchain_openai_kwargs_requires_base_url_key_and_model():
    with pytest.raises(AgencyRuntimeError) as exc:
        build_langchain_openai_kwargs(_runtime_config(base_url="", api_key="", model=""))

    assert exc.value.error_code == "EXPERT_MODEL_CONFIG_MISSING"
    assert "base_url, api_key, model" in str(exc.value)


def test_langchain_models_import_has_no_config_side_effects_under_production_debug(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "server")
    env["DEBUG"] = "false"
    for key in ("DEVICE_SECRET", "ADMIN_PASSWORD", "JWT_SECRET"):
        env.pop(key, None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.domains.ai_video_series.langchain_runtime.models; print('import-ok')",
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    assert "import-ok" in completed.stdout
