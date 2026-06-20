import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-collection-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-collection-service-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/video_production/production_collection_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/production_collection_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"


def test_collection_service_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.video_production.production_collection_service",
        "app.services.production_collection_service",
        "create_collection_from_approved_episodes",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "production_collection_service.py" in readme
    assert "app.domains.video_production.production_collection_service" in readme
    assert "app.services.production_collection_service" in readme


def test_collection_service_domain_file_owns_helper():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def create_collection_from_approved_episodes" in text
    assert "没有可打包剧集" in text


def test_legacy_collection_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.video_production import production_collection_service" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def create_collection_from_approved_episodes" not in text
    assert "db.query(Episode)" not in text


def test_legacy_collection_service_module_is_domain_module():
    for name in (
        "app.services.production_collection_service",
        "app.domains.video_production.production_collection_service",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.production_collection_service")
    domain = importlib.import_module("app.domains.video_production.production_collection_service")

    assert legacy is domain
    assert legacy.create_collection_from_approved_episodes is domain.create_collection_from_approved_episodes


def test_video_production_router_imports_collection_service_from_domain():
    text = ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.video_production.production_collection_service" in text
    assert "app.services.production_collection_service" not in text
