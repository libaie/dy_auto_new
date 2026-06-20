import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-reporting-stats-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-reporting-stats-service-domain-plan.md"
REPORTING_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-reporting-domain-design.md"
REPORTING_PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-reporting-domain-plan.md"
DOMAIN_STATS_PATH = REPO_ROOT / "server/app/domains/reporting/stats_service.py"
LEGACY_STATS_PATH = REPO_ROOT / "server/app/services/stats_service.py"
STATS_ROUTER_PATH = REPO_ROOT / "server/app/domains/reporting/stats_router.py"
DEVICE_REPORTING_PATH = REPO_ROOT / "server/app/domains/device_operations/reporting.py"
README_PATH = REPO_ROOT / "server/app/domains/reporting/README.md"


def test_reporting_stats_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.reporting.stats_service",
        "app.services.stats_service",
        "StatsService",
        "stats_service",
    ]:
        assert term in spec
        assert term in plan


def test_reporting_stats_service_domain_file_exists():
    assert DOMAIN_STATS_PATH.exists()


def test_legacy_reporting_stats_service_is_thin_facade():
    text = LEGACY_STATS_PATH.read_text(encoding="utf-8")

    assert "app.domains.reporting" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class StatsService" not in text
    assert "stats_service = StatsService()" not in text
    assert _line_count(LEGACY_STATS_PATH) <= 20


def test_legacy_reporting_stats_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.stats_service")
        domain = importlib.import_module("app.domains.reporting.stats_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"reporting stats service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.StatsService is domain.StatsService
    assert legacy.stats_service is domain.stats_service
    assert legacy._TASK_TYPE_TO_COLUMN is domain._TASK_TYPE_TO_COLUMN
    assert legacy._NURTURE_TYPE_TO_COLUMN is domain._NURTURE_TYPE_TO_COLUMN


def test_reporting_router_imports_domain_stats_service():
    text = STATS_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.reporting.stats_service" in text
    assert "app.services.stats_service" not in text


def test_device_stats_increment_route_imports_domain_stats_service_directly():
    text = DEVICE_REPORTING_PATH.read_text(encoding="utf-8")

    assert '@router.post("/stats/increment")' in text
    assert "app.domains.reporting.stats_service" in text
    assert "app.services.stats_service" not in text


def test_reporting_docs_register_stats_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    design = REPORTING_SPEC_PATH.read_text(encoding="utf-8")
    plan = REPORTING_PLAN_PATH.read_text(encoding="utf-8")

    for text in [readme, design, plan]:
        assert "app.domains.reporting.stats_service" in text
        assert "app.services.stats_service" in text
        assert "StatsService" in text or "stats_service" in text

    assert "`app.services.stats_service` -> `app.domains.reporting.stats_service`" in design
    assert 'rg "app\\.services\\.stats_service" server/app server/tests' in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
