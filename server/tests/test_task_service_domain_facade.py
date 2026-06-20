import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-task-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-task-service-domain-plan.md"
DOMAIN_TASK_SERVICE_PATH = REPO_ROOT / "server/app/domains/task_operations/task_service.py"
LEGACY_TASK_SERVICE_PATH = REPO_ROOT / "server/app/services/task_service.py"
README_PATH = REPO_ROOT / "server/app/domains/task_operations/README.md"


DOMAIN_IMPORT_PATHS = [
    REPO_ROOT / "server/app/domains/task_operations/adapters.py",
    REPO_ROOT / "server/app/domains/device_operations/status_lifecycle.py",
    REPO_ROOT / "server/app/domains/account_operations/channel_service.py",
]

FACADE_IMPORT_PATHS = [
    REPO_ROOT / "server/app/domains/device_operations/polling.py",
    REPO_ROOT / "server/app/domains/device_operations/reporting.py",
]


def test_task_service_domain_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.task_operations.task_service",
        "app.services.task_service",
        "TaskService",
        "task_service",
        "_db_task_to_pydantic",
        "MAX_RETRIES",
    ]:
        assert term in spec
        assert term in plan


def test_task_service_implementation_lives_in_task_operations_domain():
    domain_text = DOMAIN_TASK_SERVICE_PATH.read_text(encoding="utf-8")
    assert "class TaskService" in domain_text
    assert "task_service = TaskService()" in domain_text
    assert "def _db_task_to_pydantic" in domain_text
    assert "MAX_RETRIES = 3" in domain_text

    legacy_text = LEGACY_TASK_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.task_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "class TaskService" not in legacy_text
    assert "MAX_RETRIES = 3" not in legacy_text


def test_legacy_task_service_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.task_operations.task_service")
    legacy = importlib.import_module("app.services.task_service")
    assert legacy is domain
    assert legacy.TaskService is domain.TaskService
    assert legacy.task_service is domain.task_service
    assert legacy._db_task_to_pydantic is domain._db_task_to_pydantic
    assert legacy.MAX_RETRIES == domain.MAX_RETRIES


def test_domain_modules_import_task_service_from_domain_path():
    for path in DOMAIN_IMPORT_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.task_operations.task_service" in text
        assert "app.services.task_service" not in text


def test_neighbor_domains_import_task_service_through_facade():
    for path in FACADE_IMPORT_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "app.services.task_service" in text
        assert "app.domains.task_operations.task_service" not in text


def test_task_operations_readme_registers_task_service_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.task_operations.task_service" in text
    assert "app.services.task_service" in text
    assert "TaskService" in text
