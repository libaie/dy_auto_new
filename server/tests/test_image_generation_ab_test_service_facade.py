import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-ab-test-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-ab-test-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_ab_test_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_ab_test_service.py"
DOMAIN_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_ab_test_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_ab_test_service",
        "app.services.image_ab_test_service",
        "preview_ab_group",
        "create_ab_group",
        "refresh_ab_group",
        "recommend_ab_winner",
        "adopt_ab_winner",
        "mark_ab_no_winner",
        "serialize_ab_group",
    ]:
        assert term in spec
        assert term in plan


def test_image_ab_test_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_ab_test_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def preview_ab_group" not in text
    assert "async def create_ab_group" not in text
    assert "def refresh_ab_group" not in text
    assert "def adopt_ab_winner" not in text
    assert "LOGICAL_HASH_EXCLUDED_FIELDS = {" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_ab_test_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_ab_test_service")
        domain = importlib.import_module("app.domains.image_generation.image_ab_test_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image A/B test service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.preview_ab_group is domain.preview_ab_group
    assert legacy.create_ab_group is domain.create_ab_group
    assert legacy.refresh_ab_group is domain.refresh_ab_group
    assert legacy.recommend_ab_winner is domain.recommend_ab_winner
    assert legacy.adopt_ab_winner is domain.adopt_ab_winner
    assert legacy.mark_ab_no_winner is domain.mark_ab_no_winner
    assert legacy.serialize_ab_group is domain.serialize_ab_group
    assert legacy.LOGICAL_HASH_EXCLUDED_FIELDS is domain.LOGICAL_HASH_EXCLUDED_FIELDS


def test_ab_test_service_imports_domain_collaborators():
    text = DOMAIN_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_production_metrics_service" in text
    assert "app.domains.image_generation.image_production_recommendation_service" in text
    assert "app.domains.image_generation.image_selection_preview_service" in text
    assert "app.services.image_production_metrics_service" not in text
    assert "app.services.image_production_recommendation_service" not in text
    assert "app.services.image_selection_preview_service" not in text


def test_image_production_router_imports_ab_test_service_domain_path():
    text = DOMAIN_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_ab_test_service" in text
    assert "app.services.image_ab_test_service" not in text


def test_image_generation_readme_registers_ab_test_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_ab_test_service" in text
    assert "app.domains.image_generation.image_ab_test_service" in text
    assert 'rg "app\\.services\\.image_ab_test_service" server/app server/tests' in text
    assert "preview_ab_group" in text
    assert "create_ab_group" in text
    assert "serialize_ab_group" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
