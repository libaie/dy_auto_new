import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-content-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-content-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/content_collection/content_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/content_service.py"
CONTENT_GENERATION_PATH = REPO_ROOT / "server/app/domains/content_collection/content_generation.py"
MUTATIONS_PATH = REPO_ROOT / "server/app/domains/content_collection/mutations.py"
AI_GENERATOR_PATH = REPO_ROOT / "server/app/domains/model_configuration/ai_generator.py"
TASK_ADAPTERS_PATH = REPO_ROOT / "server/app/domains/task_operations/adapters.py"
CHANNEL_SERVICE_PATH = REPO_ROOT / "server/app/domains/account_operations/channel_service.py"
README_PATH = REPO_ROOT / "server/app/domains/content_collection/README.md"


def test_content_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.content_collection.content_service",
        "app.services.content_service",
        "ContentService",
    ]:
        assert term in spec
        assert term in plan


def test_content_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_content_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.content_collection" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ContentService" not in text
    assert "content_service = ContentService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_content_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.content_service")
        domain = importlib.import_module("app.domains.content_collection.content_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"content service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ContentService is domain.ContentService
    assert legacy.content_service is domain.content_service
    assert legacy._build_ac_automaton is domain._build_ac_automaton
    assert legacy._ac_contains is domain._ac_contains
    assert legacy._db_template_to_response is domain._db_template_to_response
    assert legacy._db_word_to_response is domain._db_word_to_response


def test_services_parent_package_content_service_attribute_is_domain_module():
    from app.services import content_service as parent_import

    domain = importlib.import_module("app.domains.content_collection.content_service")

    assert parent_import is domain
    assert parent_import.content_service is domain.content_service


def test_content_collection_modules_import_domain_content_service_only():
    for path in [CONTENT_GENERATION_PATH, MUTATIONS_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.content_collection.content_service" in text
        assert "app.services.content_service" not in text


def test_ai_generator_imports_domain_content_service_directly():
    for path in [AI_GENERATOR_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.content_collection.content_service" in text
        assert "app.services.content_service" not in text


def test_channel_service_imports_domain_content_service_directly():
    text = CHANNEL_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection.content_service" in text
    assert "app.services.content_service" not in text


def test_task_adapters_import_domain_content_service_directly():
    text = TASK_ADAPTERS_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection.content_service" in text
    assert "app.services.content_service" not in text


def test_content_collection_docs_register_content_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.content_collection.content_service",
        "app.services.content_service",
        "ContentService",
        "approved task/device/account bridge compatibility imports",
        "remove only when that command returns no production imports",
    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
