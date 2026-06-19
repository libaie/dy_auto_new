from fastapi.routing import APIRoute

from app.main import app


EXPECTED_ACCOUNT_OPERATION_HTTP_ROUTES = [
    ("/api/accounts", ("POST",), "create_account", "app.routers.accounts.create_account", ("get_db", "require_role:admin")),
    ("/api/accounts", ("GET",), "list_accounts", "app.routers.accounts.list_accounts", ("get_db", "verify_admin_token")),
    ("/api/accounts/{account_id}", ("GET",), "get_account", "app.routers.accounts.get_account", ("get_db", "verify_admin_token")),
    ("/api/accounts/{account_id}", ("PUT",), "update_account", "app.routers.accounts.update_account", ("get_db", "verify_admin_token")),
    ("/api/accounts/{account_id}", ("DELETE",), "delete_account", "app.routers.accounts.delete_account", ("get_db", "verify_admin_token")),
    ("/api/account-groups", ("POST",), "create_group", "app.routers.account_groups.create_group", ("get_db", "require_role:admin")),
    ("/api/account-groups", ("GET",), "list_groups", "app.routers.account_groups.list_groups", ("get_db", "verify_admin_token")),
    ("/api/account-groups/{group_id}", ("GET",), "get_group", "app.routers.account_groups.get_group", ("get_db", "verify_admin_token")),
    ("/api/account-groups/{group_id}", ("PUT",), "update_group", "app.routers.account_groups.update_group", ("get_db", "verify_admin_token")),
    ("/api/account-groups/{group_id}", ("DELETE",), "delete_group", "app.routers.account_groups.delete_group", ("get_db", "verify_admin_token")),
    ("/api/account-groups/{group_id}/members", ("GET",), "list_members", "app.routers.account_groups.list_members", ("get_db", "verify_admin_token")),
    ("/api/account-groups/{group_id}/members", ("POST",), "add_members", "app.routers.account_groups.add_members", ("get_db", "verify_admin_token")),
    ("/api/account-groups/{group_id}/members", ("DELETE",), "remove_members", "app.routers.account_groups.remove_members", ("get_db", "verify_admin_token")),
    ("/api/chains/templates", ("POST",), "create_template", "app.routers.chains.create_template", ("get_db", "require_role:admin")),
    ("/api/chains/templates", ("GET",), "list_templates", "app.routers.chains.list_templates", ("get_db", "verify_admin_token")),
    ("/api/chains/templates/{template_id}", ("GET",), "get_template", "app.routers.chains.get_template", ("get_db", "verify_admin_token")),
    ("/api/chains/templates/{template_id}", ("PUT",), "update_template", "app.routers.chains.update_template", ("get_db", "verify_admin_token")),
    ("/api/chains/templates/{template_id}", ("DELETE",), "delete_template", "app.routers.chains.delete_template", ("get_db", "verify_admin_token")),
    ("/api/chains/instances", ("POST",), "create_instances", "app.routers.chains.create_instances", ("get_db", "verify_admin_token")),
    ("/api/chains/instances", ("GET",), "list_instances", "app.routers.chains.list_instances", ("get_db", "verify_admin_token")),
    ("/api/chains/instances/{instance_id}", ("GET",), "get_instance", "app.routers.chains.get_instance", ("get_db", "verify_admin_token")),
    ("/api/chains/instances/{instance_id}/cancel", ("POST",), "cancel_instance", "app.routers.chains.cancel_instance", ("get_db", "verify_admin_token")),
    ("/api/chains/instances/{instance_id}/retry", ("POST",), "retry_instance", "app.routers.chains.retry_instance", ("get_db", "verify_admin_token")),
    ("/api/channels", ("POST",), "create_channel", "app.routers.channels.create_channel", ("get_db", "require_role:admin")),
    ("/api/channels", ("GET",), "list_channels", "app.routers.channels.list_channels", ("get_db", "verify_admin_token")),
    ("/api/channels/{channel_id}", ("GET",), "get_channel", "app.routers.channels.get_channel", ("get_db", "verify_admin_token")),
    ("/api/channels/{channel_id}", ("PATCH",), "update_channel", "app.routers.channels.update_channel", ("get_db", "verify_admin_token")),
    ("/api/channels/{channel_id}", ("DELETE",), "delete_channel", "app.routers.channels.delete_channel", ("get_db", "verify_admin_token")),
    ("/api/channels/{channel_id}/items", ("POST",), "append_items", "app.routers.channels.append_items", ("get_db", "verify_admin_token")),
    ("/api/channels/{channel_id}/items/{item_id}", ("PATCH",), "update_item", "app.routers.channels.update_item", ("get_db", "verify_admin_token")),
    ("/api/channels/items/batch", ("PUT",), "batch_edit_items", "app.routers.channels.batch_edit_items", ("get_db", "verify_admin_token")),
    ("/api/channels/items/{item_id}", ("PUT",), "edit_channel_item", "app.routers.channels.edit_channel_item", ("get_db", "verify_admin_token")),
    ("/api/channels/{channel_id}", ("PUT",), "edit_channel", "app.routers.channels.edit_channel", ("get_db", "verify_admin_token")),
]


def test_account_operation_route_table_snapshot():
    assert _account_operation_http_routes() == EXPECTED_ACCOUNT_OPERATION_HTTP_ROUTES


def test_account_operation_auth_dependency_snapshot():
    assert _dependencies_for("/api/accounts", ("POST",)) == ("get_db", "require_role:admin")
    assert _dependencies_for("/api/accounts", ("GET",)) == ("get_db", "verify_admin_token")
    assert _dependencies_for("/api/account-groups", ("POST",)) == ("get_db", "require_role:admin")
    assert _dependencies_for("/api/account-groups/{group_id}/members", ("POST",)) == ("get_db", "verify_admin_token")
    assert _dependencies_for("/api/channels", ("POST",)) == ("get_db", "require_role:admin")
    assert _dependencies_for("/api/channels/{channel_id}", ("PATCH",)) == ("get_db", "verify_admin_token")
    assert _dependencies_for("/api/chains/templates", ("POST",)) == ("get_db", "require_role:admin")
    assert _dependencies_for("/api/chains/instances", ("POST",)) == ("get_db", "verify_admin_token")


def _account_operation_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and _is_account_operation_route(route.path):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                _dependency_identity(dep.call)
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes


def _dependencies_for(path, methods):
    for route_path, route_methods, _name, _endpoint, dependencies in _account_operation_http_routes():
        if route_path == path and route_methods == methods:
            return dependencies
    raise AssertionError(f"Route not found: {methods} {path}")


def _is_account_operation_route(path):
    return (
        path == "/api/accounts"
        or path.startswith("/api/accounts/")
        or path == "/api/account-groups"
        or path.startswith("/api/account-groups/")
        or path == "/api/channels"
        or path.startswith("/api/channels/")
        or path == "/api/chains"
        or path.startswith("/api/chains/")
    )


def _dependency_identity(call):
    name = getattr(call, "__name__", repr(call))
    qualname = getattr(call, "__qualname__", "")
    if name == "checker" and qualname.endswith("require_role.<locals>.checker"):
        closure = getattr(call, "__closure__", None) or ()
        for cell in closure:
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, str):
                return f"require_role:{value}"
            if isinstance(value, (frozenset, set, tuple, list)) and value:
                roles = ",".join(sorted(str(role) for role in value))
                return f"require_role:{roles}"
    return name
