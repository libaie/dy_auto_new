import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-operations-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-operations-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_AGENCY_PATH = REPO_ROOT / "server/app/routers/agency.py"


def test_agency_operations_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.agency_operations",
        "agency_router.py",
        "app.routers.agency",
        "/api/agency",
        "AgencyExpertInvocation",
        "AgencyCreativePatch",
        "_redact_model_config_snapshot",
        "repair-tasks",
        "multimodal-review",
    ]:
        assert term in spec
        assert term in plan


def test_agency_operations_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.agency_operations")
    assert spec is not None

    import app.domains.agency_operations as domain

    assert domain.DOMAIN_NAME == "agency_operations"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/agency"


def test_agency_operations_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.agency",
        "app.domains.agency_operations.agency_router",
        "AgencyExpertInvocation",
        "AgencyCreativePatch",
        "_redact_model_config_snapshot",
        "repair-tasks",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_agency_operations_owns_router_module():
    assert (DOMAIN_PATH / "agency_router.py").exists()


def test_agency_operations_legacy_router_file_is_thin_facade():
    text = LEGACY_AGENCY_PATH.read_text(encoding="utf-8")

    assert "app.domains.agency_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_AGENCY_PATH) <= 20


def test_agency_operations_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.agency_operations import agency_router" in text
    assert "app.include_router(agency_router.router)" in text
    assert "app.include_router(agency.router)" not in text


def test_app_import_smoke_keeps_agency_operations_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/agency")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/agency/experts" in paths
    assert "/api/agency/experts/{expert_id}" in paths
    assert "/api/agency/invocations" in paths
    assert "/api/agency/invocations/{invocation_id}" in paths
    assert "/api/agency/creative-patches" in paths
    assert "/api/agency/assets/{asset_id}/multimodal-review" in paths
    assert "/api/agency/repair-tasks" in paths
    assert "/api/agency/repair-tasks/{job_id}/retry" in paths
    assert "/api/agency/repair-tasks/{job_id}/authorize-retry" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
