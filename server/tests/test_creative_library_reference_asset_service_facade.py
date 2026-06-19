import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-library-reference-asset-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-library-reference-asset-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/creative_library/reference_asset_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/reference_asset_service.py"
README_PATH = REPO_ROOT / "server/app/domains/creative_library/README.md"
DOMAIN_IMPORT_PATHS = [
    REPO_ROOT / "server/app/domains/creative_library/characters_router.py",
    REPO_ROOT / "server/app/domains/creative_library/scenes_router.py",
    REPO_ROOT / "server/app/domains/ai_video_series/style_lock.py",
    REPO_ROOT / "server/app/domains/ai_video_series/read_models.py",
]


def test_reference_asset_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.creative_library.reference_asset_service",
        "app.services.reference_asset_service",
        "ReferenceAssetError",
        "generate_reference_url",
        "generate_character_reference_images",
        "generate_scene_reference_images",
    ]:
        assert term in spec
        assert term in plan


def test_reference_asset_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_reference_asset_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.creative_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ReferenceAssetError" not in text
    assert "async def generate_reference_url" not in text
    assert "async def generate_character_reference_images" not in text
    assert "async def generate_scene_reference_images" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_reference_asset_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.reference_asset_service")
        domain = importlib.import_module("app.domains.creative_library.reference_asset_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"reference asset service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ReferenceAssetError is domain.ReferenceAssetError
    assert legacy.generate_reference_url is domain.generate_reference_url
    assert legacy.generate_character_reference_images is domain.generate_character_reference_images
    assert legacy.generate_scene_reference_images is domain.generate_scene_reference_images
    assert legacy.reference_url_is_usable is domain.reference_url_is_usable
    assert legacy.REFERENCE_SYNC_POLL_ATTEMPTS is domain.REFERENCE_SYNC_POLL_ATTEMPTS


def test_domain_modules_import_reference_asset_service_domain_path():
    for path in DOMAIN_IMPORT_PATHS:
        text = path.read_text(encoding="utf-8")

        assert "app.domains.creative_library.reference_asset_service" in text, path
        assert "app.services.reference_asset_service" not in text, path


def test_creative_library_readme_registers_reference_asset_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.reference_asset_service" in text
    assert "app.domains.creative_library.reference_asset_service" in text
    assert 'rg "app\\.services\\.reference_asset_service" server/app server/tests' in text
    assert "ReferenceAssetError" in text
    assert "generate_character_reference_images" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
