from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-prompt-management-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-prompt-management-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/prompt_management"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_PROMPT_TEMPLATES_PATH = REPO_ROOT / "server/app/routers/prompt_templates.py"


def test_prompt_management_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.prompt_management",
        "prompt_templates_router.py",
        "app.routers.prompt_templates",
        "/api/prompt-templates",
        "/api/device/prompt-templates",
        "app.routers.prompt_templates",
    ]:
        assert term in spec
        assert term in plan


def test_prompt_management_domain_exports_metadata():
    import app.domains.prompt_management as domain

    assert domain.DOMAIN_NAME == "prompt_management"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/prompt-templates"


def test_prompt_management_readme_documents_facade_and_cleanup_gates():
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.prompt_templates",
        "app.domains.prompt_management.prompt_templates_router",
        "/api/device/prompt-templates",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_prompt_management_owns_router_module():
    assert (DOMAIN_PATH / "prompt_templates_router.py").exists()


def test_prompt_management_legacy_router_file_is_thin_facade():
    text = LEGACY_PROMPT_TEMPLATES_PATH.read_text(encoding="utf-8")

    assert "app.domains.prompt_management" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_PROMPT_TEMPLATES_PATH) <= 20


def test_prompt_management_main_wiring_remains_legacy_until_pr4():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "prompt_templates" in text
    assert "app.include_router(prompt_templates.router)" in text


def test_app_import_smoke_keeps_prompt_management_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/prompt-templates")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/prompt-templates" in paths
    assert "/api/prompt-templates/generate" in paths
    assert "/api/prompt-templates/rewrite-stream" in paths
    assert "/api/prompt-templates/{name}/toggle" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
