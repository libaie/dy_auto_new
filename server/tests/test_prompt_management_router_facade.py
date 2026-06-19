import importlib
import logging

from fastapi.routing import APIRoute


EXPECTED_PROMPT_TEMPLATE_ROUTES = [
    ("POST", "/api/prompt-templates/generate", "generate_template"),
    ("POST", "/api/prompt-templates/generate-stream", "generate_template_stream"),
    ("POST", "/api/prompt-templates/rewrite-stream", "rewrite_template_stream"),
    ("GET", "/api/prompt-templates", "list_templates"),
    ("GET", "/api/prompt-templates/{name}", "get_template"),
    ("POST", "/api/prompt-templates", "create_template"),
    ("PUT", "/api/prompt-templates/{name}", "update_template"),
    ("DELETE", "/api/prompt-templates/{name}", "delete_template"),
    ("PATCH", "/api/prompt-templates/{name}/toggle", "toggle_template"),
]


def test_prompt_templates_legacy_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.prompt_templates")
    domain_router = importlib.import_module("app.domains.prompt_management.prompt_templates_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_PROMPT_TEMPLATE_ROUTES


def test_prompt_templates_domain_preserves_legacy_logger_name():
    domain_router = importlib.import_module("app.domains.prompt_management.prompt_templates_router")

    assert domain_router.logger is logging.getLogger("app.routers.prompt_templates")


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot
