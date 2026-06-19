import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-seedance-integration-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-seedance-integration-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/seedance_integration"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_ROUTER_PATH = REPO_ROOT / "server/app/routers/seedance.py"


def test_seedance_integration_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.seedance_integration",
        "seedance_router.py",
        "app.routers.seedance",
        "/api/seedance",
        "/api/seedance-proxy",
        "SeedanceGenerateRequest",
        "SEEDANCE_MODEL_ID",
        "_get_api_key",
        "_get_client",
        "_do_proxy",
    ]:
        assert term in spec
        assert term in plan


def test_seedance_integration_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.seedance_integration")
    assert spec is not None

    import app.domains.seedance_integration as domain

    assert domain.DOMAIN_NAME == "seedance_integration"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/seedance"
    assert domain.PUBLIC_PROXY_PREFIX == "/api/seedance-proxy"


def test_seedance_integration_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.seedance",
        "app.domains.seedance_integration.seedance_router",
        "SeedanceGenerateRequest",
        "SEEDANCE_MODEL_ID",
        "_get_api_key",
        "_get_client",
        "_do_proxy",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_seedance_integration_domain_owns_router_module():
    assert (DOMAIN_PATH / "seedance_router.py").exists()


def test_seedance_integration_legacy_router_file_is_thin_facade():
    text = LEGACY_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.seedance_integration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_ROUTER_PATH) <= 20


def test_seedance_integration_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.seedance_integration import seedance_router" in text
    assert "app.include_router(seedance_router.api_router)" in text
    assert "app.include_router(seedance_router.proxy_router)" in text
    assert "app.include_router(seedance.api_router)" not in text
    assert "app.include_router(seedance.proxy_router)" not in text


def test_app_import_smoke_keeps_seedance_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute)
        and (route.path.startswith("/api/seedance") or route.path.startswith("/api/seedance-proxy"))
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/seedance/generate" in paths
    assert "/api/seedance/task/{task_id}" in paths
    assert "/api/seedance-proxy/{path:path}" in paths
    assert "/api/seedance-proxy/" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
