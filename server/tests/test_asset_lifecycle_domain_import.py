import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-asset-lifecycle-domain-import-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-asset-lifecycle-domain-import-plan.md"
SERIES_ROUTER_PATH = REPO_ROOT / "server/app/domains/ai_video_series/router.py"


def test_asset_lifecycle_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.asset_lifecycle_service",
        "app.services.asset_lifecycle_service",
        "ai_video_series.router",
    ]:
        assert term in spec
        assert term in plan


def test_series_router_imports_asset_lifecycle_from_domain_path():
    text = SERIES_ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.asset_lifecycle_service" in text
    assert "app.services.asset_lifecycle_service" not in text


def test_legacy_asset_lifecycle_facade_still_resolves_to_domain_module():
    legacy = importlib.import_module("app.services.asset_lifecycle_service")
    domain = importlib.import_module("app.domains.creative_library.asset_lifecycle_service")
    assert legacy is domain
    assert legacy.AssetLifecycleError is domain.AssetLifecycleError
    assert legacy.delete_or_archive_series is domain.delete_or_archive_series
