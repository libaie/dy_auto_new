import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-review-asset-edit-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-review-asset-edit-domain-plan.md"
DOMAIN_EDIT_PATH = REPO_ROOT / "server/app/domains/video_production/review_asset_edit_service.py"
LEGACY_EDIT_PATH = REPO_ROOT / "server/app/services/review_asset_edit_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_review_asset_edit_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.review_asset_edit_service",
        "app.services.review_asset_edit_service",
        "edit_image_asset",
        "void_asset_version",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_review_asset_edit_domain_file_exists():
    assert DOMAIN_EDIT_PATH.exists()


def test_legacy_video_production_review_asset_edit_is_thin_facade():
    text = LEGACY_EDIT_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ReviewAssetEditError" not in text
    assert "def void_asset_version" not in text
    assert "async def edit_image_asset" not in text
    assert _line_count(LEGACY_EDIT_PATH) <= 20


def test_legacy_video_production_review_asset_edit_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.review_asset_edit_service")
        domain = importlib.import_module("app.domains.video_production.review_asset_edit_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production review asset edit domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ReviewAssetEditError is domain.ReviewAssetEditError
    assert legacy._generate_edited_image is domain._generate_edited_image
    assert legacy.edit_image_asset is domain.edit_image_asset
    assert legacy.void_asset_version is domain.void_asset_version


def test_video_production_router_imports_domain_review_asset_edit_service():
    text = ROUTER_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_production.review_asset_edit_service import (" in text
    assert "from app.services.review_asset_edit_service import (" not in text


def test_video_production_readme_registers_review_asset_edit_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.review_asset_edit_service" in text
    assert "app.domains.video_production.review_asset_edit_service" in text
    assert 'rg "app\\.services\\.review_asset_edit_service" server/app server/tests' in text
    assert "edit_image_asset" in text
    assert "void_asset_version" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
