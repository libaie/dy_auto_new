from fastapi.routing import APIRoute

from app.main import app


EXPECTED_TASK_OPERATION_HTTP_ROUTES = [
    ("/api/tasks", ("POST",), "create_task", "app.domains.task_operations.tasks_router.create_task", ("get_db", "verify_admin_token")),
    ("/api/tasks/batch", ("POST",), "batch_create_tasks", "app.domains.task_operations.tasks_router.batch_create_tasks", ("get_db", "verify_admin_token")),
    ("/api/tasks", ("GET",), "list_tasks", "app.domains.task_operations.tasks_router.list_tasks", ("get_db", "verify_admin_token")),
    ("/api/tasks/batch-delete", ("POST",), "batch_delete_tasks", "app.domains.task_operations.tasks_router.batch_delete_tasks", ("get_db", "verify_admin_token")),
    ("/api/tasks/{task_id}", ("GET",), "get_task", "app.domains.task_operations.tasks_router.get_task", ("get_db", "verify_admin_token")),
    ("/api/tasks/{task_id}/cancel", ("POST",), "cancel_task", "app.domains.task_operations.tasks_router.cancel_task", ("get_db", "verify_admin_token")),
    ("/api/tasks/{task_id}", ("DELETE",), "delete_task", "app.domains.task_operations.tasks_router.delete_task", ("get_db", "verify_admin_token")),
]


def test_task_operation_route_table_snapshot():
    assert _task_operation_http_routes() == EXPECTED_TASK_OPERATION_HTTP_ROUTES


def test_task_operation_auth_dependency_snapshot():
    for path, methods, _name, _endpoint, expected_dependencies in EXPECTED_TASK_OPERATION_HTTP_ROUTES:
        assert _dependencies_for(path, methods) == expected_dependencies


def _task_operation_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and _is_task_operation_route(route.path):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                _dependency_identity(dep.call)
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes


def _dependencies_for(path, methods):
    for route_path, route_methods, _name, _endpoint, dependencies in _task_operation_http_routes():
        if route_path == path and route_methods == methods:
            return dependencies
    raise AssertionError(f"Route not found: {methods} {path}")


def _is_task_operation_route(path):
    return path == "/api/tasks" or path.startswith("/api/tasks/")


def _dependency_identity(call):
    return getattr(call, "__name__", repr(call))
