import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-identity-access-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-identity-access-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/identity_access"
DEVICE_OPERATIONS_PATH = REPO_ROOT / "server/app/domains/device_operations"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_AUTH_PATH = REPO_ROOT / "server/app/routers/auth.py"


def test_identity_access_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.identity_access",
        "auth_router.py",
        "app.routers.auth",
        "/api/auth",
        "_failed_attempts",
        "app.deps",
        "device_operations",
    ]:
        assert term in spec
        assert term in plan


def test_identity_access_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.identity_access")
    assert spec is not None

    import app.domains.identity_access as domain

    assert domain.DOMAIN_NAME == "identity_access"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/auth"


def test_identity_access_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.auth",
        "app.domains.identity_access.auth_router",
        "_failed_attempts",
        "app.deps",
        "device_operations",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_identity_access_owns_router_module():
    assert (DOMAIN_PATH / "auth_router.py").exists()


def test_identity_access_legacy_router_file_is_thin_facade():
    text = LEGACY_AUTH_PATH.read_text(encoding="utf-8")

    assert "app.domains.identity_access" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_AUTH_PATH) <= 20


def test_identity_access_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.identity_access import auth_router" in text
    assert "app.include_router(auth_router.router)" in text
    assert "app.include_router(auth.router)" not in text


def test_identity_access_keeps_device_operations_separate():
    operations_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in DEVICE_OPERATIONS_PATH.glob("*.py")
    )

    assert "app.domains.identity_access" not in operations_text
    assert "auth_router" not in operations_text


def test_app_import_smoke_keeps_identity_access_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/auth")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/auth/login" in paths
    assert "/api/auth/device-login" in paths
    assert "/api/auth/register" in paths
    assert "/api/auth/users" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
