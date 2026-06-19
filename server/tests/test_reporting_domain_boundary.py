import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-reporting-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-reporting-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/reporting"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_STATS_PATH = REPO_ROOT / "server/app/routers/stats.py"
DEVICE_REPORTING_PATH = REPO_ROOT / "server/app/domains/device_operations/reporting.py"


def test_reporting_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.reporting",
        "stats_router.py",
        "app.routers.stats",
        "/api/stats",
        "/api/device/stats/increment",
        "app.services.stats_service",
    ]:
        assert term in spec
        assert term in plan


def test_reporting_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.reporting")
    assert spec is not None

    import app.domains.reporting as domain

    assert domain.DOMAIN_NAME == "reporting"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/stats"


def test_reporting_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.stats",
        "app.domains.reporting.stats_router",
        "/api/device/stats/increment",
        "app.services.stats_service",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_reporting_owns_router_module():
    assert (DOMAIN_PATH / "stats_router.py").exists()


def test_reporting_legacy_router_file_is_thin_facade():
    text = LEGACY_STATS_PATH.read_text(encoding="utf-8")

    assert "app.domains.reporting" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_STATS_PATH) <= 20


def test_reporting_main_keeps_legacy_router_until_direct_wiring():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "app.include_router(stats.router)" in text


def test_reporting_keeps_device_stats_increment_in_device_operations():
    reporting = DEVICE_REPORTING_PATH.read_text(encoding="utf-8")

    assert '@router.post("/stats/increment")' in reporting
    assert "app.domains.reporting" not in reporting


def test_app_import_smoke_keeps_reporting_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/stats")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/stats/dashboard" in paths
    assert "/api/stats/daily" in paths
    assert "/api/stats/accounts/{account_id}" in paths
    assert "/api/stats/realtime" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
