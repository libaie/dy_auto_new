import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-script-pipeline-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-script-pipeline-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/script_pipeline/script_pipeline_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/script_pipeline.py"
README_PATH = REPO_ROOT / "server/app/domains/script_pipeline/README.md"


def test_script_pipeline_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.script_pipeline.script_pipeline_service",
        "app.services.script_pipeline",
        "DynamicPromptBuilder",
        "ScriptGenerationPipeline",
        "PipelineManager",
    ]:
        assert term in spec
        assert term in plan


def test_script_pipeline_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_script_pipeline_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.script_pipeline" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class DynamicPromptBuilder" not in text
    assert "class ScriptGenerationPipeline" not in text
    assert "class PipelineManager" not in text
    assert "pipeline_router" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_script_pipeline_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.script_pipeline")
        domain = importlib.import_module("app.domains.script_pipeline.script_pipeline_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"script pipeline service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.DynamicPromptBuilder is domain.DynamicPromptBuilder
    assert legacy.ScriptGenerationPipeline is domain.ScriptGenerationPipeline
    assert legacy.PipelineManager is domain.PipelineManager
    assert legacy.ScriptGenerationError is domain.ScriptGenerationError


def test_script_pipeline_readme_registers_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.script_pipeline" in text
    assert "app.domains.script_pipeline.script_pipeline_service" in text
    assert 'rg "app\\.services\\.script_pipeline" server/app server/tests' in text
    assert "DynamicPromptBuilder" in text
    assert "PipelineManager" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
