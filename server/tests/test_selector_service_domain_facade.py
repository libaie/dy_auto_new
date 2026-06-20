import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-selector-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-selector-service-domain-plan.md"
SELECTOR_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-selector-management-domain-design.md"
SELECTOR_PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-selector-management-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/selector_management/selector_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/selector_service.py"
SELECTORS_ROUTER_PATH = REPO_ROOT / "server/app/domains/selector_management/selectors_router.py"
DEVICE_SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"
README_PATH = REPO_ROOT / "server/app/domains/selector_management/README.md"


def test_selector_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.selector_management.selector_service",
        "app.services.selector_service",
        "SelectorService",
        "selector_service",
        "_bump_revision",
    ]:
        assert term in spec
        assert term in plan


def test_selector_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_selector_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.selector_management" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class SelectorService" not in text
    assert "selector_service = SelectorService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_selector_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.selector_service")
        domain = importlib.import_module("app.domains.selector_management.selector_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"selector service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.SelectorService is domain.SelectorService
    assert legacy.selector_service is domain.selector_service
    assert legacy._bump_revision is domain._bump_revision
    assert legacy._aspect_tag is domain._aspect_tag
    assert legacy._profile_priority is domain._profile_priority


def test_selectors_router_imports_domain_selector_service_only():
    text = SELECTORS_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.selector_management.selector_service" in text
    assert "app.services.selector_service" not in text
    assert "app.domains.selector_management.template_service" in text


def test_device_selectors_import_domain_service_directly():
    text = DEVICE_SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")

    assert '@router.get("/selectors")' in text
    assert "app.domains.selector_management.selector_service" in text
    assert "app.services.selector_service" not in text


def test_selector_management_docs_register_selector_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    design = SELECTOR_SPEC_PATH.read_text(encoding="utf-8")
    plan = SELECTOR_PLAN_PATH.read_text(encoding="utf-8")

    for text in [readme, design, plan]:
        assert "app.domains.selector_management.selector_service" in text
        assert "app.services.selector_service" in text
        assert "SelectorService" in text or "selector_service" in text

    assert 'rg "app\\.services\\.selector_service" server/app server/tests' in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
