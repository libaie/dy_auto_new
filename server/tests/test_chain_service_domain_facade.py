import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-chain-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-chain-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/account_operations/chain_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/chain_service.py"
ADAPTERS_PATH = REPO_ROOT / "server/app/domains/account_operations/adapters.py"
TASK_SERVICE_PATH = REPO_ROOT / "server/app/services/task_service.py"
README_PATH = REPO_ROOT / "server/app/domains/account_operations/README.md"


def test_chain_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.account_operations.chain_service",
        "app.services.chain_service",
        "ChainService",
    ]:
        assert term in spec
        assert term in plan


def test_chain_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_chain_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.account_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ChainService" not in text
    assert "chain_service = ChainService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_chain_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.chain_service")
        domain = importlib.import_module("app.domains.account_operations.chain_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"chain service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ChainService is domain.ChainService
    assert legacy.chain_service is domain.chain_service
    assert legacy._account_lock is domain._account_lock
    assert legacy.VALID_STEP_TYPES is domain.VALID_STEP_TYPES
    assert legacy._task_to_push_dict is domain._task_to_push_dict


def test_services_parent_package_chain_service_attribute_is_domain_module():
    from app.services import chain_service as parent_import

    domain = importlib.import_module("app.domains.account_operations.chain_service")

    assert parent_import is domain
    assert parent_import.chain_service is domain.chain_service


def test_account_operations_adapters_imports_domain_chain_service_only():
    text = ADAPTERS_PATH.read_text(encoding="utf-8")

    assert "app.domains.account_operations.chain_service" in text
    assert "app.services.chain_service" not in text


def test_task_service_stays_legacy_compatible():
    text = TASK_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.services.chain_service" not in text
    assert "app.domains.account_operations.chain_service" not in text


def test_account_operations_docs_register_chain_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.account_operations.chain_service",
        "app.services.chain_service",
        "ChainService",
        "legacy imports remain only compatibility tests or migration docs",

    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
