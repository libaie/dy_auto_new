from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-task-operations-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
FUTURE_DOMAIN_PATH = REPO_ROOT / "server/app/domains/task_operations"
FUTURE_DOMAIN_README_PATH = FUTURE_DOMAIN_PATH / "README.md"
LEGACY_TASKS_ROUTER_PATH = REPO_ROOT / "server/app/routers/tasks.py"
DEVICE_OPERATIONS_PATH = REPO_ROOT / "server/app/domains/device_operations"
ACCOUNT_OPERATIONS_PATH = REPO_ROOT / "server/app/domains/account_operations"
CONTENT_COLLECTION_PATH = REPO_ROOT / "server/app/domains/content_collection"


def test_task_operations_future_contract_is_documented_in_plan():
    text = PLAN_PATH.read_text(encoding="utf-8")

    required_terms = [
        "app.domains.task_operations",
        "__init__.py",
        "tasks_router.py",
        "schemas.py",
        "read_models.py",
        "param_resolution.py",
        "task_use_cases.py",
        "realtime_events.py",
        "adapters.py",
        'DOMAIN_NAME = "task_operations"',
        'PUBLIC_ROUTE_PREFIX = "/api/tasks"',
        "device_operations",
        "account_operations",
        "content_collection",
    ]
    for term in required_terms:
        assert term in text


def test_task_operations_domain_package_exports_metadata_only_skeleton():
    import app.domains.task_operations as domain

    assert domain.DOMAIN_NAME == "task_operations"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/tasks"


def test_task_operations_readme_documents_facades_and_cleanup_gates():
    text = FUTURE_DOMAIN_README_PATH.read_text(encoding="utf-8")

    required_terms = [
        "Facade Register",
        "app.routers.tasks",
        "app.domains.task_operations.tasks_router",
        "device_operations",
        "account_operations",
        "content_collection",
        "new_task_available",
        "task_updated",
        "tasks_changed",
        "cancel_task",
        "Compatibility Cleanup Gates",
    ]
    for term in required_terms:
        assert term in text


def test_task_operations_pr2_does_not_create_router_module_yet():
    assert not (FUTURE_DOMAIN_PATH / "tasks_router.py").exists()


def test_task_operations_pr1_keeps_legacy_router_file_active():
    text = LEGACY_TASKS_ROUTER_PATH.read_text(encoding="utf-8")

    assert 'APIRouter(prefix="/api/tasks"' in text
    assert "app.domains.task_operations" not in text
    assert "pair_ws_manager" in text
    assert "_maybe_resolve_content_template" in text
    assert "_maybe_resolve_dm_sequence" in text


def test_task_operations_pr1_does_not_wire_domain_in_main():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "app.domains.task_operations" not in text
    assert "from app.routers import tasks" in text
    assert "app.include_router(tasks.router)" in text


def test_task_operations_explicitly_stays_out_of_neighbor_domains():
    task_text = LEGACY_TASKS_ROUTER_PATH.read_text(encoding="utf-8")

    assert "task_operations" not in (DEVICE_OPERATIONS_PATH / "polling.py").read_text(encoding="utf-8")
    assert "task_operations" not in (DEVICE_OPERATIONS_PATH / "reporting.py").read_text(encoding="utf-8")
    assert "task_operations" not in (ACCOUNT_OPERATIONS_PATH / "chain_use_cases.py").read_text(encoding="utf-8")
    assert "task_operations" not in (CONTENT_COLLECTION_PATH / "mutations.py").read_text(encoding="utf-8")
    assert "app.domains.device_operations" not in task_text
    assert "app.domains.account_operations" not in task_text


def test_app_import_smoke_keeps_task_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and (route.path == "/api/tasks" or route.path.startswith("/api/tasks/"))
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/tasks" in paths
    assert "/api/tasks/batch" in paths
    assert "/api/tasks/batch-delete" in paths
    assert "/api/tasks/{task_id}" in paths
    assert "/api/tasks/{task_id}/cancel" in paths
