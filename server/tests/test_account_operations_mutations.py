from fastapi.routing import APIRoute

from app.main import app


ACCOUNT_MUTATION_ENDPOINTS = {
    "/api/accounts": {"create_account", "list_accounts"},
    "/api/accounts/{account_id}": {"get_account", "update_account", "delete_account"},
    "/api/account-groups": {"create_group", "list_groups"},
    "/api/account-groups/{group_id}": {"get_group", "update_group", "delete_group"},
    "/api/account-groups/{group_id}/members": {"list_members", "add_members", "remove_members"},
    "/api/channels": {"create_channel", "list_channels"},
    "/api/channels/{channel_id}": {"get_channel", "update_channel", "delete_channel", "edit_channel"},
    "/api/channels/{channel_id}/items": {"append_items"},
    "/api/channels/{channel_id}/items/{item_id}": {"update_item"},
    "/api/channels/items/batch": {"batch_edit_items"},
    "/api/channels/items/{item_id}": {"edit_channel_item"},
}


def test_account_group_and_channel_routes_stay_on_domain_routers():
    seen = {}
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path in ACCOUNT_MUTATION_ENDPOINTS:
            seen.setdefault(route.path, set()).add(route.name)
            if route.path.startswith("/api/accounts"):
                assert route.endpoint.__module__ == "app.domains.account_operations.accounts_router"
            elif route.path.startswith("/api/account-groups"):
                assert route.endpoint.__module__ == "app.domains.account_operations.account_groups_router"
            elif route.path.startswith("/api/channels"):
                assert route.endpoint.__module__ == "app.domains.account_operations.channels_router"

    assert seen == ACCOUNT_MUTATION_ENDPOINTS


def test_account_operation_use_case_modules_export_expected_functions():
    import app.domains.account_operations.account_use_cases as account_use_cases
    import app.domains.account_operations.adapters as adapters
    import app.domains.account_operations.channel_use_cases as channel_use_cases
    import app.domains.account_operations.chain_use_cases as chain_use_cases
    import app.domains.account_operations.group_use_cases as group_use_cases
    import app.domains.account_operations.realtime_events as realtime_events

    for name in ("create_account", "list_accounts", "get_account", "update_account", "delete_account"):
        assert hasattr(account_use_cases, name)

    for name in (
        "create_group",
        "list_groups",
        "get_group",
        "update_group",
        "delete_group",
        "list_members",
        "add_members",
        "remove_members",
    ):
        assert hasattr(group_use_cases, name)

    for name in (
        "create_channel",
        "list_channels",
        "get_channel",
        "update_channel_status",
        "delete_channel",
        "append_items",
        "update_item_status",
        "batch_edit_items",
        "edit_channel_item",
        "edit_channel",
    ):
        assert hasattr(channel_use_cases, name)

    for name in (
        "broadcast_accounts_changed",
        "broadcast_account_groups_changed",
        "broadcast_channels_changed",
        "broadcast_new_task_available",
        "broadcast_chains_changed",
        "send_cancel_task",
    ):
        assert hasattr(realtime_events, name)

    for name in ("chain_service", "channel_service"):
        assert hasattr(adapters, name)

    for name in (
        "create_template",
        "list_templates",
        "get_template",
        "update_template",
        "delete_template",
        "create_instances",
        "list_instances",
        "get_instance",
        "cancel_instance",
        "retry_instance",
    ):
        assert hasattr(chain_use_cases, name)
