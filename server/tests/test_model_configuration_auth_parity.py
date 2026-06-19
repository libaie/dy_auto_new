from fastapi.routing import APIRoute

from app.main import app


EXPECTED_MODEL_CONFIGURATION_HTTP_ROUTES = [
    (
        "/api/ai-models",
        ("GET",),
        "list_models",
        "app.domains.model_configuration.ai_models_router.list_models",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/ai-models/options",
        ("GET",),
        "get_options",
        "app.domains.model_configuration.ai_models_router.get_options",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/ai-models/schema",
        ("GET",),
        "get_schema",
        "app.domains.model_configuration.ai_models_router.get_schema",
        ("verify_admin_token",),
    ),
    (
        "/api/ai-models/{model_id}",
        ("GET",),
        "get_model",
        "app.domains.model_configuration.ai_models_router.get_model",
        ("get_db", "checker"),
    ),
    (
        "/api/ai-models",
        ("POST",),
        "create_model",
        "app.domains.model_configuration.ai_models_router.create_model",
        ("get_db", "checker"),
    ),
    (
        "/api/ai-models/{model_id}",
        ("PUT",),
        "update_model",
        "app.domains.model_configuration.ai_models_router.update_model",
        ("get_db", "checker"),
    ),
    (
        "/api/ai-models/{model_id}",
        ("DELETE",),
        "delete_model",
        "app.domains.model_configuration.ai_models_router.delete_model",
        ("get_db", "checker"),
    ),
    (
        "/api/ai-models/{model_id}/test",
        ("POST",),
        "test_connection",
        "app.domains.model_configuration.ai_models_router.test_connection",
        ("get_db", "checker"),
    ),
]


def test_model_configuration_route_table_snapshot():
    assert _model_configuration_http_routes() == EXPECTED_MODEL_CONFIGURATION_HTTP_ROUTES


def _model_configuration_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/ai-models"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes
