import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-selector-template-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-selector-template-service-domain-plan.md"
SELECTOR_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-selector-management-domain-design.md"
SELECTOR_PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-selector-management-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/selector_management/template_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/template_service.py"
SELECTORS_ROUTER_PATH = REPO_ROOT / "server/app/domains/selector_management/selectors_router.py"
DEVICE_SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"
README_PATH = REPO_ROOT / "server/app/domains/selector_management/README.md"
TEMPLATE_DIR_PATH = REPO_ROOT / "server/app/template_images"


def test_selector_template_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.selector_management.template_service",
        "app.services.template_service",
        "TemplateService",
        "template_service",
        "TEMPLATE_DIR",
    ]:
        assert term in spec
        assert term in plan


def test_selector_template_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_template_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.selector_management" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class TemplateService" not in text
    assert "template_service = TemplateService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_template_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.template_service")
        domain = importlib.import_module("app.domains.selector_management.template_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"selector template service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.TemplateService is domain.TemplateService
    assert legacy.template_service is domain.template_service
    assert legacy.TEMPLATE_DIR is domain.TEMPLATE_DIR
    assert legacy._aspect_tag is domain._aspect_tag
    assert legacy._same_aspect_dirs is domain._same_aspect_dirs
    assert legacy._safe_resolve is domain._safe_resolve


def test_services_parent_package_template_service_attribute_is_domain_module():
    from app.services import template_service as parent_import

    domain = importlib.import_module("app.domains.selector_management.template_service")

    assert parent_import is domain
    assert parent_import.template_service is domain.template_service


def test_template_dir_stays_under_server_app_template_images():
    domain = importlib.import_module("app.domains.selector_management.template_service")

    assert domain.TEMPLATE_DIR == TEMPLATE_DIR_PATH
    assert domain.TEMPLATE_DIR.name == "template_images"
    assert domain.TEMPLATE_DIR.parent == REPO_ROOT / "server/app"


def test_selectors_router_imports_domain_template_service_only():
    text = SELECTORS_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.selector_management.template_service" in text
    assert "app.services.template_service" not in text


def test_device_template_routes_stay_device_owned_and_legacy_compatible():
    text = DEVICE_SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")

    assert '.get("/templates")' in text
    assert '.get("/templates/{filename}")' in text
    assert "app.services.template_service" in text
    assert "app.domains.selector_management.template_service" not in text


def test_selector_management_docs_register_template_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    design = SELECTOR_SPEC_PATH.read_text(encoding="utf-8")
    plan = SELECTOR_PLAN_PATH.read_text(encoding="utf-8")

    for text in [readme, design, plan]:
        assert "app.domains.selector_management.template_service" in text
        assert "app.services.template_service" in text
        assert "TemplateService" in text or "template_service" in text

    assert 'rg "app\\.services\\.template_service" server/app server/tests' in readme
    assert "server/app/template_images" in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
