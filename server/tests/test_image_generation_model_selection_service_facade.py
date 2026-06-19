import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-model-selection-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-model-selection-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_model_selection_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_model_selection_service.py"
DOMAIN_SELECTION_PREVIEW_PATH = REPO_ROOT / "server/app/domains/image_generation/image_selection_preview_service.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_model_selection_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_model_selection_service",
        "app.services.image_model_selection_service",
        "resolve_image_model_selection",
        "_selected_model_payload",
        "_fallback_model_payload",
    ]:
        assert term in spec
        assert term in plan


def test_image_model_selection_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_model_selection_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def resolve_image_model_selection" not in text
    assert "def _selected_model_payload" not in text
    assert "def _fallback_model_payload" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_model_selection_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_model_selection_service")
        domain = importlib.import_module("app.domains.image_generation.image_model_selection_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image model selection service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.resolve_image_model_selection is domain.resolve_image_model_selection
    assert legacy._selected_model_payload is domain._selected_model_payload
    assert legacy._rejected_candidate is domain._rejected_candidate
    assert legacy._fallback_model_payload is domain._fallback_model_payload


def test_selection_preview_imports_model_selection_service_domain_path():
    text = DOMAIN_SELECTION_PREVIEW_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_model_selection_service" in text
    assert "app.services.image_model_selection_service" not in text


def test_image_generation_readme_registers_model_selection_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_model_selection_service" in text
    assert "app.domains.image_generation.image_model_selection_service" in text
    assert 'rg "app\\.services\\.image_model_selection_service" server/app server/tests' in text
    assert "resolve_image_model_selection" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
