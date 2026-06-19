from fastapi.routing import APIRoute

from app.main import app


CHAIN_ENDPOINTS = {
    "/api/chains/templates": {"create_template", "list_templates"},
    "/api/chains/templates/{template_id}": {"get_template", "update_template", "delete_template"},
    "/api/chains/instances": {"create_instances", "list_instances"},
    "/api/chains/instances/{instance_id}": {"get_instance"},
    "/api/chains/instances/{instance_id}/cancel": {"cancel_instance"},
    "/api/chains/instances/{instance_id}/retry": {"retry_instance"},
}


def test_chain_routes_stay_on_domain_router():
    seen = {}
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path in CHAIN_ENDPOINTS:
            seen.setdefault(route.path, set()).add(route.name)
            assert route.endpoint.__module__ == "app.domains.account_operations.chains_router"

    assert seen == CHAIN_ENDPOINTS


def test_chain_use_cases_keep_device_polling_out_of_domain():
    import app.domains.account_operations.chain_use_cases as chain_use_cases
    import app.domains.account_operations.realtime_events as realtime_events

    assert hasattr(chain_use_cases, "cancel_instance")
    assert hasattr(chain_use_cases, "retry_instance")
    assert hasattr(realtime_events, "send_cancel_task")
    assert not hasattr(chain_use_cases, "poll_tasks")
    assert not hasattr(chain_use_cases, "report_result")
    assert not hasattr(chain_use_cases, "heartbeat")
