import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-device-reporting-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-device-reporting-domain-imports-plan.md"
REPORTING_PATH = REPO_ROOT / "server/app/domains/device_operations/reporting.py"


def test_device_reporting_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.reporting.stats_service",
        "app.domains.account_operations.channel_service",
        "app.services.stats_service",
        "app.services.channel_service",
    ]:
        assert term in spec
        assert term in plan


def test_device_reporting_imports_helpers_from_domain_paths():
    text = REPORTING_PATH.read_text(encoding="utf-8")
    assert "app.domains.reporting.stats_service" in text
    assert "app.domains.account_operations.channel_service" in text
    assert "app.services.stats_service" not in text
    assert "app.services.channel_service" not in text


def test_legacy_reporting_and_channel_facades_resolve_to_domain_modules():
    stats_legacy = importlib.import_module("app.services.stats_service")
    stats_domain = importlib.import_module("app.domains.reporting.stats_service")
    channel_legacy = importlib.import_module("app.services.channel_service")
    channel_domain = importlib.import_module("app.domains.account_operations.channel_service")
    assert stats_legacy is stats_domain
    assert stats_legacy.stats_service is stats_domain.stats_service
    assert channel_legacy is channel_domain
    assert channel_legacy.channel_service is channel_domain.channel_service
