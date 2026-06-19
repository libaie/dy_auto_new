import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-policy-runtime-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-policy-runtime-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_policy_runtime.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_production_policy_runtime.py"
DOMAIN_SELECTION_PREVIEW_PATH = REPO_ROOT / "server/app/domains/image_generation/image_selection_preview_service.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_policy_runtime_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_production_policy_runtime",
        "app.services.image_production_policy_runtime",
        "estimate_image_cost",
        "preview_image_capacity",
        "preview_review_gate",
    ]:
        assert term in spec
        assert term in plan


def test_image_policy_runtime_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_policy_runtime_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def estimate_image_cost" not in text
    assert "def preview_image_capacity" not in text
    assert "def preview_review_gate" not in text
    assert "DEFAULT_COST_POLICY = {" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_policy_runtime_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_production_policy_runtime")
        domain = importlib.import_module("app.domains.image_generation.image_production_policy_runtime")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image production policy runtime domain import failed: {exc}")

    assert legacy is domain
    assert legacy.estimate_image_cost is domain.estimate_image_cost
    assert legacy.preview_image_capacity is domain.preview_image_capacity
    assert legacy.preview_review_gate is domain.preview_review_gate
    assert legacy.DEFAULT_COST_POLICY is domain.DEFAULT_COST_POLICY


def test_selection_preview_imports_policy_runtime_domain_path():
    text = DOMAIN_SELECTION_PREVIEW_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_production_policy_runtime" in text
    assert "app.services.image_production_policy_runtime" not in text


def test_image_generation_readme_registers_policy_runtime_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_production_policy_runtime" in text
    assert "app.domains.image_generation.image_production_policy_runtime" in text
    assert 'rg "app\\.services\\.image_production_policy_runtime" server/app server/tests' in text
    assert "estimate_image_cost" in text
    assert "preview_image_capacity" in text
    assert "preview_review_gate" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
