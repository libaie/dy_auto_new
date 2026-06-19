import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-asset-bridge-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-asset-bridge-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_asset_bridge_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_asset_bridge_service.py"
DOMAIN_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_asset_bridge_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_asset_bridge_service",
        "app.services.image_asset_bridge_service",
        "promote_image_asset_to_video_asset",
        "video_asset_payload",
    ]:
        assert term in spec
        assert term in plan


def test_image_asset_bridge_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_asset_bridge_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def promote_image_asset_to_video_asset" not in text
    assert "def video_asset_payload" not in text
    assert "def _validate_scope" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_asset_bridge_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_asset_bridge_service")
        domain = importlib.import_module("app.domains.image_generation.image_asset_bridge_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image asset bridge domain import failed: {exc}")

    assert legacy is domain
    assert legacy.promote_image_asset_to_video_asset is domain.promote_image_asset_to_video_asset
    assert legacy.video_asset_payload is domain.video_asset_payload
    assert legacy._validate_scope is domain._validate_scope
    assert legacy._metadata is domain._metadata


def test_image_production_router_imports_asset_bridge_domain_path():
    text = DOMAIN_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_asset_bridge_service" in text
    assert "app.services.image_asset_bridge_service" not in text


def test_image_generation_readme_registers_asset_bridge_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_asset_bridge_service" in text
    assert "app.domains.image_generation.image_asset_bridge_service" in text
    assert 'rg "app\\.services\\.image_asset_bridge_service" server/app server/tests' in text
    assert "promote_image_asset_to_video_asset" in text
    assert "video_asset_payload" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
