import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-error-helper-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-error-helper-domain-plan.md"
DOMAIN_HELPER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_creation_errors.py"
LEGACY_HELPER_PATH = REPO_ROOT / "server/app/services/image_creation_errors.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"
DOMAIN_FILES = [
    REPO_ROOT / "server/app/domains/image_generation/image_ab_test_service.py",
    REPO_ROOT / "server/app/domains/image_generation/image_asset_bridge_service.py",
    REPO_ROOT / "server/app/domains/image_generation/image_creation_router.py",
    REPO_ROOT / "server/app/domains/image_generation/image_production_recommendation_service.py",
    REPO_ROOT / "server/app/domains/image_generation/image_production_strategy_service.py",
    REPO_ROOT / "server/app/domains/image_generation/image_selection_preview_service.py",
]


def test_image_error_helper_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_creation_errors",
        "app.services.image_creation_errors",
        "image_error",
    ]:
        assert term in spec
        assert term in plan


def test_image_error_helper_domain_file_exists():
    assert DOMAIN_HELPER_PATH.exists()


def test_legacy_image_error_helper_is_thin_facade():
    text = LEGACY_HELPER_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def image_error" not in text
    assert "HTTPException(" not in text
    assert _line_count(LEGACY_HELPER_PATH) <= 20


def test_legacy_image_error_helper_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_creation_errors")
        domain = importlib.import_module("app.domains.image_generation.image_creation_errors")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image error helper domain import failed: {exc}")

    assert legacy is domain
    assert legacy.image_error is domain.image_error


def test_domain_modules_import_error_helper_domain_path():
    for path in DOMAIN_FILES:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.image_generation.image_creation_errors" in text, path
        assert "app.services.image_creation_errors" not in text, path


def test_image_generation_readme_registers_error_helper_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_creation_errors" in text
    assert "app.domains.image_generation.image_creation_errors" in text
    assert 'rg "app\\.services\\.image_creation_errors" server/app server/tests' in text
    assert "image_error" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
