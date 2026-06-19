import importlib
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_ACCOUNTS_ROUTER_SNAPSHOT = [
    ("POST", "/api/accounts", "create_account"),
    ("GET", "/api/accounts", "list_accounts"),
    ("GET", "/api/accounts/{account_id}", "get_account"),
    ("PUT", "/api/accounts/{account_id}", "update_account"),
    ("DELETE", "/api/accounts/{account_id}", "delete_account"),
]

EXPECTED_ACCOUNT_GROUPS_ROUTER_SNAPSHOT = [
    ("POST", "/api/account-groups", "create_group"),
    ("GET", "/api/account-groups", "list_groups"),
    ("GET", "/api/account-groups/{group_id}", "get_group"),
    ("PUT", "/api/account-groups/{group_id}", "update_group"),
    ("DELETE", "/api/account-groups/{group_id}", "delete_group"),
    ("GET", "/api/account-groups/{group_id}/members", "list_members"),
    ("POST", "/api/account-groups/{group_id}/members", "add_members"),
    ("DELETE", "/api/account-groups/{group_id}/members", "remove_members"),
]

EXPECTED_CHANNELS_ROUTER_SNAPSHOT = [
    ("POST", "/api/channels", "create_channel"),
    ("GET", "/api/channels", "list_channels"),
    ("GET", "/api/channels/{channel_id}", "get_channel"),
    ("PATCH", "/api/channels/{channel_id}", "update_channel"),
    ("DELETE", "/api/channels/{channel_id}", "delete_channel"),
    ("POST", "/api/channels/{channel_id}/items", "append_items"),
    ("PATCH", "/api/channels/{channel_id}/items/{item_id}", "update_item"),
    ("PUT", "/api/channels/items/batch", "batch_edit_items"),
    ("PUT", "/api/channels/items/{item_id}", "edit_channel_item"),
    ("PUT", "/api/channels/{channel_id}", "edit_channel"),
]

EXPECTED_CHAINS_ROUTER_SNAPSHOT = [
    ("POST", "/api/chains/templates", "create_template"),
    ("GET", "/api/chains/templates", "list_templates"),
    ("GET", "/api/chains/templates/{template_id}", "get_template"),
    ("PUT", "/api/chains/templates/{template_id}", "update_template"),
    ("DELETE", "/api/chains/templates/{template_id}", "delete_template"),
    ("POST", "/api/chains/instances", "create_instances"),
    ("GET", "/api/chains/instances", "list_instances"),
    ("GET", "/api/chains/instances/{instance_id}", "get_instance"),
    ("POST", "/api/chains/instances/{instance_id}/cancel", "cancel_instance"),
    ("POST", "/api/chains/instances/{instance_id}/retry", "retry_instance"),
]


def test_domain_accounts_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.account_operations.accounts_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_ACCOUNTS_ROUTER_SNAPSHOT


def test_domain_account_groups_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.account_operations.account_groups_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_ACCOUNT_GROUPS_ROUTER_SNAPSHOT


def test_domain_channels_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.account_operations.channels_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_CHANNELS_ROUTER_SNAPSHOT


def test_domain_chains_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.account_operations.chains_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_CHAINS_ROUTER_SNAPSHOT


def test_legacy_accounts_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.accounts")
    domain_router = importlib.import_module("app.domains.account_operations.accounts_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_legacy_account_groups_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.account_groups")
    domain_router = importlib.import_module("app.domains.account_operations.account_groups_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_legacy_channels_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.channels")
    domain_router = importlib.import_module("app.domains.account_operations.channels_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_legacy_chains_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.chains")
    domain_router = importlib.import_module("app.domains.account_operations.chains_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_router_facade_cleanup_gates_are_documented():
    readme = (REPO_ROOT / "server/app/domains/account_operations/README.md").read_text(encoding="utf-8")

    assert "Compatibility Cleanup Gates" in readme
    assert "Do not remove `app.routers.accounts`, `app.routers.account_groups`, `app.routers.channels`, or `app.routers.chains` until all of these are true" in readme


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot
