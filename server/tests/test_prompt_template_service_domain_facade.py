import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-prompt-template-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-prompt-template-service-domain-plan.md"
PROMPT_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-prompt-management-domain-design.md"
PROMPT_PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-prompt-management-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/prompt_management/prompt_template_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/prompt_template_service.py"
PROMPT_ROUTER_PATH = REPO_ROOT / "server/app/domains/prompt_management/prompt_templates_router.py"
DEVICE_SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"
README_PATH = REPO_ROOT / "server/app/domains/prompt_management/README.md"


def test_prompt_template_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.prompt_management.prompt_template_service",
        "app.services.prompt_template_service",
        "PromptTemplateService",
        "prompt_template_service",
        "PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES",
    ]:
        assert term in spec
        assert term in plan


def test_prompt_template_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_prompt_template_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.prompt_management" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class PromptTemplateService" not in text
    assert "prompt_template_service = PromptTemplateService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_prompt_template_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.prompt_template_service")
        domain = importlib.import_module("app.domains.prompt_management.prompt_template_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"prompt template service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.PromptTemplateService is domain.PromptTemplateService
    assert legacy.prompt_template_service is domain.prompt_template_service
    assert legacy.PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS is domain.PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS
    assert legacy.PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES is domain.PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES
    assert legacy._get_tmpl_revision is domain._get_tmpl_revision
    assert legacy._set_tmpl_revision is domain._set_tmpl_revision
    assert legacy._bump_tmpl_revision is domain._bump_tmpl_revision
    assert legacy._to_dict is domain._to_dict
    assert legacy._to_device_dict is domain._to_device_dict


def test_services_parent_package_prompt_template_service_attribute_is_domain_module():
    from app.services import prompt_template_service as parent_import

    domain = importlib.import_module("app.domains.prompt_management.prompt_template_service")

    assert parent_import is domain
    assert parent_import.prompt_template_service is domain.prompt_template_service


def test_prompt_router_imports_domain_prompt_template_service_only():
    text = PROMPT_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.prompt_management.prompt_template_service" in text
    assert "app.services.prompt_template_service" not in text


def test_legacy_router_facade_preserves_prompt_template_service_patch_path():
    legacy_router = importlib.import_module("app.routers.prompt_templates")
    domain_router = importlib.import_module("app.domains.prompt_management.prompt_templates_router")
    service_domain = importlib.import_module("app.domains.prompt_management.prompt_template_service")

    assert legacy_router is domain_router
    assert legacy_router.prompt_template_service is service_domain.prompt_template_service
    assert domain_router.prompt_template_service is service_domain.prompt_template_service


def test_device_prompt_templates_stay_device_owned_and_legacy_compatible():
    text = DEVICE_SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")

    assert '@router.get("/prompt-templates")' in text
    assert "app.services.prompt_template_service" in text
    assert "app.domains.prompt_management.prompt_template_service" not in text


def test_prompt_management_docs_register_prompt_template_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    design = PROMPT_SPEC_PATH.read_text(encoding="utf-8")
    plan = PROMPT_PLAN_PATH.read_text(encoding="utf-8")

    for text in [readme, design, plan]:
        assert "app.domains.prompt_management.prompt_template_service" in text
        assert "app.services.prompt_template_service" in text
        assert "PromptTemplateService" in text or "prompt_template_service" in text

    assert 'rg "app\\.services\\.prompt_template_service" server/app server/tests' in readme
    assert "app.routers.prompt_templates.prompt_template_service" in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
