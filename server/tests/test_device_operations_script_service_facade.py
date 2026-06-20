import importlib
import io
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-device-script-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-device-script-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/device_operations/script_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/script_service.py"
SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"
README_PATH = REPO_ROOT / "server/app/domains/device_operations/README.md"


def test_script_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.device_operations.script_service",
        "app.services.script_service",
        "ScriptService",
    ]:
        assert term in spec
        assert term in plan


def test_script_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_script_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.device_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ScriptService" not in text
    assert "script_service = ScriptService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 12


def test_legacy_script_service_module_is_domain_module():
    legacy = importlib.import_module("app.services.script_service")
    domain = importlib.import_module("app.domains.device_operations.script_service")
    assert legacy is domain
    assert legacy.ScriptService is domain.ScriptService
    assert legacy.script_service is domain.script_service


def test_services_parent_package_script_service_attribute_is_domain_module():
    from app.services import script_service as parent_import

    domain = importlib.import_module("app.domains.device_operations.script_service")
    assert parent_import is domain


def test_script_assets_import_domain_script_service_only():
    text = SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")
    assert "app.domains.device_operations.script_service" in text
    assert "app.services.script_service" not in text


def test_device_operations_docs_register_script_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.device_operations.script_service",
        "app.services.script_service",
        "ScriptService",
        "SERVER_DIR / `scripts`",
    ]:
        assert term in readme


def test_script_service_upload_download_behavior_stays_legacy_compatible(tmp_path):
    legacy = importlib.import_module("app.services.script_service")
    service = legacy.ScriptService(tmp_path / "scripts", tmp_path / "scripts" / "version.txt")
    assert service.get_version() == "0.0.0"
    assert service.download_script() is None
    version = service.upload_script(io.BytesIO(b"PK\x03\x04zip"))
    assert version == "0.0.1"
    assert service.download_script() == b"PK\x03\x04zip"


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
