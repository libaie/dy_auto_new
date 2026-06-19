import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-asset-storage-guard-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-asset-storage-guard-domain-plan.md"
DOMAIN_STORAGE_PATH = REPO_ROOT / "server/app/domains/video_production/asset_storage_guard.py"
LEGACY_STORAGE_PATH = REPO_ROOT / "server/app/services/asset_storage_guard.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_asset_storage_guard_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.asset_storage_guard",
        "app.services.asset_storage_guard",
        "ALLOWED_PROVIDER_SCHEMES",
        "ALLOWED_IMAGE_MAGIC",
        "ALLOWED_VIDEO_MAGIC",
        "persist_provider_asset",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_asset_storage_guard_domain_file_exists():
    assert DOMAIN_STORAGE_PATH.exists()


def test_legacy_video_production_asset_storage_guard_is_thin_facade():
    text = LEGACY_STORAGE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "ALLOWED_PROVIDER_SCHEMES =" not in text
    assert "def _storage_failed" not in text
    assert "def persist_provider_asset" not in text
    assert _line_count(LEGACY_STORAGE_PATH) <= 20


def test_legacy_video_production_asset_storage_guard_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.asset_storage_guard")
        domain = importlib.import_module("app.domains.video_production.asset_storage_guard")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production asset storage guard domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ALLOWED_PROVIDER_SCHEMES is domain.ALLOWED_PROVIDER_SCHEMES
    assert legacy.ALLOWED_IMAGE_MAGIC is domain.ALLOWED_IMAGE_MAGIC
    assert legacy.ALLOWED_VIDEO_MAGIC is domain.ALLOWED_VIDEO_MAGIC
    assert legacy.persist_provider_asset is domain.persist_provider_asset


def test_legacy_video_production_asset_storage_guard_monkeypatch_path_resolves_to_domain_module():
    import app.services as services_package

    legacy = importlib.import_module("app.services.asset_storage_guard")
    domain = importlib.import_module("app.domains.video_production.asset_storage_guard")

    assert legacy is domain
    assert services_package.asset_storage_guard is domain
    assert legacy.httpx is domain.httpx


def test_video_production_asset_storage_guard_imports_domain_errors():
    text = DOMAIN_STORAGE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_errors" in text
    assert "app.services.production_errors" not in text


def test_video_production_router_imports_domain_asset_storage_guard():
    text = ROUTER_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_production.asset_storage_guard import persist_provider_asset" in text
    assert "from app.services.asset_storage_guard import persist_provider_asset" not in text


def test_video_production_readme_registers_asset_storage_guard_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.asset_storage_guard" in text
    assert "app.domains.video_production.asset_storage_guard" in text
    assert 'rg "app\\.services\\.asset_storage_guard" server/app server/tests' in text
    assert "ALLOWED_PROVIDER_SCHEMES" in text
    assert "persist_provider_asset" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
