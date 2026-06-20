import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-device-config-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-device-config-domain-imports-plan.md"
POLLING_PATH = REPO_ROOT / "server/app/domains/device_operations/polling.py"
SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"


def test_device_config_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.prompt_management.prompt_template_service",
        "app.domains.selector_management.selector_service",
        "app.domains.selector_management.template_service",
        "app.services.prompt_template_service",
        "app.services.selector_service",
        "app.services.template_service",
    ]:
        assert term in spec
        assert term in plan


def test_device_operations_import_config_helpers_from_domain_paths():
    polling = POLLING_PATH.read_text(encoding="utf-8")
    script_assets = SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")
    for text in [polling, script_assets]:
        assert "app.domains.prompt_management.prompt_template_service" in text
        assert "app.domains.selector_management.selector_service" in text
        assert "app.services.prompt_template_service" not in text
        assert "app.services.selector_service" not in text
    assert "app.domains.selector_management.template_service" in script_assets
    assert "app.services.template_service" not in script_assets


def test_legacy_device_config_facades_still_resolve_to_domain_modules():
    prompt_legacy = importlib.import_module("app.services.prompt_template_service")
    prompt_domain = importlib.import_module("app.domains.prompt_management.prompt_template_service")
    selector_legacy = importlib.import_module("app.services.selector_service")
    selector_domain = importlib.import_module("app.domains.selector_management.selector_service")
    template_legacy = importlib.import_module("app.services.template_service")
    template_domain = importlib.import_module("app.domains.selector_management.template_service")
    assert prompt_legacy is prompt_domain
    assert prompt_legacy.prompt_template_service is prompt_domain.prompt_template_service
    assert selector_legacy is selector_domain
    assert selector_legacy.selector_service is selector_domain.selector_service
    assert template_legacy is template_domain
    assert template_legacy.template_service is template_domain.template_service
