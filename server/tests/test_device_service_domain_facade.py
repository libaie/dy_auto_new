import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-device-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-device-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/device_operations/device_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/device_service.py"
README_PATH = REPO_ROOT / "server/app/domains/device_operations/README.md"
DEVICE_MODULES = [
    REPO_ROOT / "server/app/domains/device_operations/device_router.py",
    REPO_ROOT / "server/app/domains/device_operations/polling.py",
    REPO_ROOT / "server/app/domains/device_operations/reporting.py",
    REPO_ROOT / "server/app/domains/device_operations/status_ws.py",
]


def test_device_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.device_operations.device_service",
        "app.services.device_service",
        "DeviceService",
    ]:
        assert term in spec
        assert term in plan


def test_device_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_device_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.device_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class DeviceService" not in text
    assert "device_service = DeviceService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_device_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.device_service")
        domain = importlib.import_module("app.domains.device_operations.device_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"device service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.DeviceService is domain.DeviceService
    assert legacy.device_service is domain.device_service


def test_services_parent_package_device_service_attribute_is_domain_module():
    from app.services import device_service as parent_import

    domain = importlib.import_module("app.domains.device_operations.device_service")

    assert parent_import is domain
    assert parent_import.device_service is domain.device_service


def test_device_operations_modules_import_domain_device_service_only():
    for path in DEVICE_MODULES:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.device_operations.device_service" in text
        assert "app.services.device_service" not in text


def test_device_operations_docs_register_device_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.device_operations.device_service",
        "app.services.device_service",
        "DeviceService",
        'rg -n "app\\.services\\.device_service" server/app -g "*.py"',
    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
