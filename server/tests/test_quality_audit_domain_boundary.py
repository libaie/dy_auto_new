import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-quality-audit-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-quality-audit-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/quality_audit"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_AUDIT_PATH = REPO_ROOT / "server/app/routers/audit.py"
VIDEO_PRODUCTION_SERVICE_PATH = REPO_ROOT / "server/app/services/video_production_service.py"


def test_quality_audit_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.quality_audit",
        "audit_router.py",
        "app.routers.audit",
        "/api/audit",
        "AuditReport",
        "AuditImageRequest",
        "_do_audit",
        "_audit_openai_compatible",
        "video_production_service.py",
    ]:
        assert term in spec
        assert term in plan


def test_quality_audit_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.quality_audit")
    assert spec is not None

    import app.domains.quality_audit as domain

    assert domain.DOMAIN_NAME == "quality_audit"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/audit"


def test_quality_audit_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.audit",
        "app.domains.quality_audit.audit_router",
        "AuditImageRequest",
        "AuditReport",
        "_do_audit",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_quality_audit_owns_router_module():
    assert (DOMAIN_PATH / "audit_router.py").exists()


def test_quality_audit_legacy_router_file_is_thin_facade():
    text = LEGACY_AUDIT_PATH.read_text(encoding="utf-8")

    assert "app.domains.quality_audit" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_AUDIT_PATH) <= 20


def test_quality_audit_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.quality_audit import audit_router" in text
    assert "app.include_router(audit_router.router)" in text
    assert "app.include_router(audit.router)" not in text


def test_video_production_service_imports_domain_audit_helper():
    text = VIDEO_PRODUCTION_SERVICE_PATH.read_text(encoding="utf-8")

    assert "from app.domains.quality_audit.audit_router import _do_audit" in text
    assert "from app.routers.audit import _do_audit" not in text


def test_app_import_smoke_keeps_quality_audit_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/audit")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/audit/image" in paths
    assert "/api/audit/reports/{target_type}/{target_id}" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
