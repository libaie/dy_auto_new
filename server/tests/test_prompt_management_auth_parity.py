from fastapi.routing import APIRoute

from app.main import app


EXPECTED_PROMPT_MANAGEMENT_HTTP_ROUTES = [
    ("/api/prompt-templates/generate", ("POST",), "generate_template", "app.domains.prompt_management.prompt_templates_router.generate_template", ("get_db", "verify_admin_token")),
    ("/api/prompt-templates/generate-stream", ("POST",), "generate_template_stream", "app.domains.prompt_management.prompt_templates_router.generate_template_stream", ("get_db", "verify_admin_token")),
    ("/api/prompt-templates/rewrite-stream", ("POST",), "rewrite_template_stream", "app.domains.prompt_management.prompt_templates_router.rewrite_template_stream", ("checker",)),
    ("/api/prompt-templates", ("GET",), "list_templates", "app.domains.prompt_management.prompt_templates_router.list_templates", ("get_db", "verify_admin_token")),
    ("/api/prompt-templates/{name}", ("GET",), "get_template", "app.domains.prompt_management.prompt_templates_router.get_template", ("get_db", "verify_admin_token")),
    ("/api/prompt-templates", ("POST",), "create_template", "app.domains.prompt_management.prompt_templates_router.create_template", ("get_db", "checker")),
    ("/api/prompt-templates/{name}", ("PUT",), "update_template", "app.domains.prompt_management.prompt_templates_router.update_template", ("get_db", "checker")),
    ("/api/prompt-templates/{name}", ("DELETE",), "delete_template", "app.domains.prompt_management.prompt_templates_router.delete_template", ("get_db", "checker")),
    ("/api/prompt-templates/{name}/toggle", ("PATCH",), "toggle_template", "app.domains.prompt_management.prompt_templates_router.toggle_template", ("get_db", "checker")),
]


def test_prompt_management_route_table_snapshot():
    assert _prompt_management_http_routes() == EXPECTED_PROMPT_MANAGEMENT_HTTP_ROUTES


def _prompt_management_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/prompt-templates"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes
