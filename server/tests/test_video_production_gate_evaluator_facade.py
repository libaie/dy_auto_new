import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-gate-evaluator-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-gate-evaluator-domain-plan.md"
DOMAIN_GATE_PATH = REPO_ROOT / "server/app/domains/video_production/production_gate_evaluator.py"
LEGACY_GATE_PATH = REPO_ROOT / "server/app/services/production_gate_evaluator.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_gate_evaluator_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_gate_evaluator",
        "app.services.production_gate_evaluator",
        "evaluate_stage_gate",
        "STAGE_ASSET_TYPES",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_gate_evaluator_domain_file_exists():
    assert DOMAIN_GATE_PATH.exists()


def test_legacy_video_production_gate_evaluator_is_thin_facade():
    text = LEGACY_GATE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "STAGE_ASSET_TYPES =" not in text
    assert "def evaluate_stage_gate" not in text
    assert _line_count(LEGACY_GATE_PATH) <= 20


def test_legacy_video_production_gate_evaluator_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_gate_evaluator")
        domain = importlib.import_module("app.domains.video_production.production_gate_evaluator")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production gate evaluator domain import failed: {exc}")

    assert legacy is domain
    assert legacy.STAGE_ASSET_TYPES is domain.STAGE_ASSET_TYPES
    assert legacy.evaluate_stage_gate is domain.evaluate_stage_gate


def test_video_production_gate_evaluator_imports_domain_state_helper():
    text = DOMAIN_GATE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.video_production_state" in text
    assert "app.services.video_production_state" not in text


def test_video_production_readme_registers_gate_evaluator_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_gate_evaluator" in text
    assert "app.domains.video_production.production_gate_evaluator" in text
    assert 'rg "app\\.services\\.production_gate_evaluator" server/app server/tests' in text
    assert "evaluate_stage_gate" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
