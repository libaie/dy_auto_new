import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-selection-preview-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-selection-preview-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_selection_preview_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_selection_preview_service.py"
DOMAIN_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_selection_preview_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_selection_preview_service",
        "app.services.image_selection_preview_service",
        "create_selection_preview",
        "_validate_provider_options",
        "ImageSelectionPreview",
    ]:
        assert term in spec
        assert term in plan


def test_image_selection_preview_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_selection_preview_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def create_selection_preview" not in text
    assert "def _validate_provider_options" not in text
    assert "ImageSelectionPreview(" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_selection_preview_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_selection_preview_service")
        domain = importlib.import_module("app.domains.image_generation.image_selection_preview_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image selection preview service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.create_selection_preview is domain.create_selection_preview
    assert legacy._validate_provider_options is domain._validate_provider_options
    assert legacy._get_strategy is domain._get_strategy
    assert legacy._selected_model_payload is domain._selected_model_payload


def test_image_production_router_imports_selection_preview_service_domain_path():
    text = DOMAIN_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_selection_preview_service" in text
    assert "app.services.image_selection_preview_service" not in text


def test_image_generation_readme_registers_selection_preview_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_selection_preview_service" in text
    assert "app.domains.image_generation.image_selection_preview_service" in text
    assert 'rg "app\\.services\\.image_selection_preview_service" server/app server/tests' in text
    assert "create_selection_preview" in text
    assert "ImageSelectionPreview" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
