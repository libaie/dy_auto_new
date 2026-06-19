import importlib
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_TASKS_ROUTER_SNAPSHOT = [
    ("POST", "/api/tasks", "create_task"),
    ("POST", "/api/tasks/batch", "batch_create_tasks"),
    ("GET", "/api/tasks", "list_tasks"),
    ("POST", "/api/tasks/batch-delete", "batch_delete_tasks"),
    ("GET", "/api/tasks/{task_id}", "get_task"),
    ("POST", "/api/tasks/{task_id}/cancel", "cancel_task"),
    ("DELETE", "/api/tasks/{task_id}", "delete_task"),
]


def test_domain_tasks_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.task_operations.tasks_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_TASKS_ROUTER_SNAPSHOT


def test_legacy_tasks_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.tasks")
    domain_router = importlib.import_module("app.domains.task_operations.tasks_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_router_facade_cleanup_gates_are_documented():
    readme = (REPO_ROOT / "server/app/domains/task_operations/README.md").read_text(encoding="utf-8")

    assert "Compatibility Cleanup Gates" in readme
    assert "Do not remove `app.routers.tasks` until all of these are true" in readme


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot
