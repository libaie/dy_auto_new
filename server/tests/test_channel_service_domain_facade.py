import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-channel-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-channel-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/account_operations/channel_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/channel_service.py"
ACCOUNT_ADAPTERS_PATH = REPO_ROOT / "server/app/domains/account_operations/adapters.py"
TASK_SERVICE_PATH = REPO_ROOT / "server/app/services/task_service.py"
TASK_ADAPTERS_PATH = REPO_ROOT / "server/app/domains/task_operations/adapters.py"
DEVICE_REPORTING_PATH = REPO_ROOT / "server/app/domains/device_operations/reporting.py"
README_PATH = REPO_ROOT / "server/app/domains/account_operations/README.md"


def test_channel_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.account_operations.channel_service",
        "app.services.channel_service",
        "ChannelService",
    ]:
        assert term in spec
        assert term in plan


def test_channel_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_channel_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.account_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ChannelService" not in text
    assert "channel_service = ChannelService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_channel_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.channel_service")
        domain = importlib.import_module("app.domains.account_operations.channel_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"channel service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ChannelService is domain.ChannelService
    assert legacy.channel_service is domain.channel_service
    assert legacy.MAX_KEYWORDS is domain.MAX_KEYWORDS
    assert legacy._busy_account_ids is domain._busy_account_ids
    assert legacy._unique_nonempty is domain._unique_nonempty
    assert legacy._inject_nurture_keyword_matrix is domain._inject_nurture_keyword_matrix
    assert legacy._resolve_nurture_subtask_templates is domain._resolve_nurture_subtask_templates
    assert legacy._get_active_accounts is domain._get_active_accounts


def test_services_parent_package_channel_service_attribute_is_domain_module():
    from app.services import channel_service as parent_import

    domain = importlib.import_module("app.domains.account_operations.channel_service")

    assert parent_import is domain
    assert parent_import.channel_service is domain.channel_service


def test_account_operations_adapters_imports_domain_channel_service_only():
    text = ACCOUNT_ADAPTERS_PATH.read_text(encoding="utf-8")

    assert "app.domains.account_operations.channel_service" in text
    assert "app.services.channel_service" not in text


def test_task_and_device_bridges_stay_legacy_compatible():
    for path in [TASK_SERVICE_PATH, TASK_ADAPTERS_PATH, DEVICE_REPORTING_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.services.channel_service" in text
        assert "app.domains.account_operations.channel_service" not in text


def test_account_operations_docs_register_channel_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.account_operations.channel_service",
        "app.services.channel_service",
        "ChannelService",
        "approved task/device bridge compatibility imports",
        "remove only when that command returns no production imports",
    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
