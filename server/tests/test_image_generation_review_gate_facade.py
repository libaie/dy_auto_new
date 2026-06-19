import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-review-gate-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-review-gate-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_review_gate_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_review_gate_service.py"
DOMAIN_ASSET_BRIDGE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_asset_bridge_service.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_review_gate_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_review_gate_service",
        "app.services.image_review_gate_service",
        "asset_review_gate",
        "review_gate_passed",
        "review_gate_rescue_actions",
    ]:
        assert term in spec
        assert term in plan


def test_image_review_gate_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_review_gate_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def asset_review_gate" not in text
    assert "def review_gate_passed" not in text
    assert "def review_gate_rescue_actions" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_review_gate_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_review_gate_service")
        domain = importlib.import_module("app.domains.image_generation.image_review_gate_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image review gate domain import failed: {exc}")

    assert legacy is domain
    assert legacy.asset_review_gate is domain.asset_review_gate
    assert legacy.review_gate_passed is domain.review_gate_passed
    assert legacy.review_gate_rescue_actions is domain.review_gate_rescue_actions


def test_asset_bridge_imports_review_gate_domain_path():
    text = DOMAIN_ASSET_BRIDGE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_review_gate_service" in text
    assert "app.services.image_review_gate_service" not in text


def test_image_generation_readme_registers_review_gate_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_review_gate_service" in text
    assert "app.domains.image_generation.image_review_gate_service" in text
    assert 'rg "app\\.services\\.image_review_gate_service" server/app server/tests' in text
    assert "asset_review_gate" in text
    assert "review_gate_passed" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
