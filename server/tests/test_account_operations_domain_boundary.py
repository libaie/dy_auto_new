from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-18-account-operations-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
TASKS_ROUTER_PATH = REPO_ROOT / "server/app/routers/tasks.py"
FUTURE_DOMAIN_PATH = REPO_ROOT / "server/app/domains/account_operations"
FUTURE_DOMAIN_README_PATH = FUTURE_DOMAIN_PATH / "README.md"

LEGACY_ROUTER_PATHS = {
    "accounts": (REPO_ROOT / "server/app/routers/accounts.py", 'APIRouter(prefix="/api/accounts"'),
    "account_groups": (REPO_ROOT / "server/app/routers/account_groups.py", 'APIRouter(prefix="/api/account-groups"'),
    "channels": (REPO_ROOT / "server/app/routers/channels.py", 'APIRouter(prefix="/api/channels"'),
    "chains": (REPO_ROOT / "server/app/routers/chains.py", 'APIRouter(prefix="/api/chains"'),
}


def test_account_operations_future_contract_is_documented_in_plan():
    text = PLAN_PATH.read_text(encoding="utf-8")

    required_terms = [
        "app.domains.account_operations",
        "__init__.py",
        "accounts_router.py",
        "account_groups_router.py",
        "channels_router.py",
        "chains_router.py",
        "schemas.py",
        "read_models.py",
        "account_use_cases.py",
        "group_use_cases.py",
        "channel_use_cases.py",
        "chain_use_cases.py",
        "realtime_events.py",
        "adapters.py",
        'DOMAIN_NAME = "account_operations"',
        '("/api/accounts", "/api/account-groups", "/api/channels", "/api/chains")',
    ]
    for term in required_terms:
        assert term in text


def test_account_operations_domain_package_exports_metadata_only_skeleton():
    import app.domains.account_operations as domain

    assert domain.DOMAIN_NAME == "account_operations"
    assert domain.PUBLIC_ROUTE_PREFIXES == ("/api/accounts", "/api/account-groups", "/api/channels", "/api/chains")


def test_account_operations_readme_documents_facades_and_cleanup_gates():
    text = FUTURE_DOMAIN_README_PATH.read_text(encoding="utf-8")

    required_terms = [
        "Facade Register",
        "app.routers.accounts",
        "app.domains.account_operations.accounts_router",
        "app.routers.account_groups",
        "app.domains.account_operations.account_groups_router",
        "app.routers.channels",
        "app.domains.account_operations.channels_router",
        "app.routers.chains",
        "app.domains.account_operations.chains_router",
        "server/app/routers/tasks.py",
        "Compatibility Cleanup Gates",
    ]
    for term in required_terms:
        assert term in text


def test_account_operations_pr2_does_not_create_router_modules_yet():
    assert not (FUTURE_DOMAIN_PATH / "accounts_router.py").exists()
    assert not (FUTURE_DOMAIN_PATH / "account_groups_router.py").exists()
    assert not (FUTURE_DOMAIN_PATH / "channels_router.py").exists()
    assert not (FUTURE_DOMAIN_PATH / "chains_router.py").exists()


def test_account_operations_pr1_keeps_legacy_router_files_active():
    for _name, (path, prefix) in LEGACY_ROUTER_PATHS.items():
        text = path.read_text(encoding="utf-8")
        assert prefix in text
        assert "app.domains.account_operations" not in text
        assert "pair_ws_manager" in text


def test_account_operations_pr1_does_not_wire_domain_in_main():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "app.domains.account_operations" not in text
    assert "app.include_router(accounts.router)" in text
    assert "app.include_router(account_groups.router)" in text
    assert "app.include_router(channels.router)" in text
    assert "app.include_router(chains.router)" in text


def test_tasks_router_remains_outside_account_operations_pr1():
    plan_text = PLAN_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_ROUTER_PATH.read_text(encoding="utf-8")

    assert "server/app/routers/tasks.py" in plan_text
    assert "Stays outside this domain" in plan_text
    assert "app.domains.account_operations" not in tasks_text


def test_app_import_smoke_keeps_account_operation_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and _is_account_operation_route(route.path)
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/accounts" in paths
    assert "/api/account-groups" in paths
    assert "/api/channels" in paths
    assert "/api/chains/templates" in paths
    assert "/api/chains/instances" in paths


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
