import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-channel-service-domain-dependencies-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-channel-service-domain-dependencies-plan.md"
CHANNEL_SERVICE_PATH = REPO_ROOT / "server/app/domains/account_operations/channel_service.py"


def test_channel_dependency_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.content_collection.content_service",
        "app.domains.reporting.stats_service",
        "app.services.content_service",
        "app.services.stats_service",
    ]:
        assert term in spec
        assert term in plan


def test_channel_service_imports_dependencies_from_domain_paths():
    text = CHANNEL_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection.content_service" in text
    assert "app.domains.reporting.stats_service" in text
    assert "app.services.content_service" not in text
    assert "app.services.stats_service" not in text


def test_legacy_content_and_stats_facades_resolve_to_domain_modules():
    content_legacy = importlib.import_module("app.services.content_service")
    content_domain = importlib.import_module("app.domains.content_collection.content_service")
    stats_legacy = importlib.import_module("app.services.stats_service")
    stats_domain = importlib.import_module("app.domains.reporting.stats_service")
    assert content_legacy is content_domain
    assert content_legacy.content_service is content_domain.content_service
    assert stats_legacy is stats_domain
    assert stats_legacy.stats_service is stats_domain.stats_service
