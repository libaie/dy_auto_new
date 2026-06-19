from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-18-content-collection-domain-plan.md"
FUTURE_DOMAIN_PATH = REPO_ROOT / "server/app/domains/content_collection"
FUTURE_DOMAIN_README_PATH = FUTURE_DOMAIN_PATH / "README.md"
CONTENT_ROUTER_PATH = REPO_ROOT / "server/app/routers/content.py"
DATA_ROUTER_PATH = REPO_ROOT / "server/app/routers/data.py"
DM_SEQUENCES_ROUTER_PATH = REPO_ROOT / "server/app/routers/dm_sequences.py"


def test_content_collection_future_contract_is_documented_in_plan():
    text = PLAN_PATH.read_text(encoding="utf-8")

    required_terms = [
        "app.domains.content_collection",
        "__init__.py",
        "content_router.py",
        "data_router.py",
        "dm_sequences_router.py",
        "read_models.py",
        "content_generation.py",
        "collection_reports.py",
        "dm_claims.py",
        "mutations.py",
        "realtime_events.py",
        "adapters.py",
        'DOMAIN_NAME = "content_collection"',
        '("/api/content", "/api/data", "/api/dm-sequences")',
        "device_operations.content_bridge",
    ]
    for term in required_terms:
        assert term in text


def test_content_collection_domain_package_exports_metadata_only_skeleton():
    import app.domains.content_collection as domain

    assert domain.DOMAIN_NAME == "content_collection"
    assert domain.PUBLIC_ROUTE_PREFIXES == ("/api/content", "/api/data", "/api/dm-sequences")


def test_content_collection_readme_documents_facades_and_cleanup_gates():
    text = FUTURE_DOMAIN_README_PATH.read_text(encoding="utf-8")

    required_terms = [
        "Facade Register",
        "app.routers.content",
        "app.domains.content_collection.content_router",
        "app.routers.data",
        "app.domains.content_collection.data_router",
        "app.routers.dm_sequences",
        "app.domains.content_collection.dm_sequences_router",
        "app.domains.device_operations.content_bridge",
        "Compatibility Cleanup Gates",
    ]
    for term in required_terms:
        assert term in text


def test_content_collection_legacy_router_files_still_own_behavior_in_pr1():
    content_text = CONTENT_ROUTER_PATH.read_text(encoding="utf-8")
    data_text = DATA_ROUTER_PATH.read_text(encoding="utf-8")
    dm_text = DM_SEQUENCES_ROUTER_PATH.read_text(encoding="utf-8")

    assert "APIRouter(prefix=\"/api/content\"" in content_text
    assert "APIRouter(prefix=\"/api/data\"" in data_text
    assert "APIRouter(prefix=\"/api/dm-sequences\"" in dm_text
    assert "app.domains.content_collection" not in content_text
    assert "app.domains.content_collection" not in data_text
    assert "app.domains.content_collection" not in dm_text


def test_app_import_smoke_keeps_content_collection_routes_registered():
    from app.main import app

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/api/content/templates" in paths
    assert "/api/data/comments" in paths
    assert "/api/data/export/users" in paths
    assert "/api/dm-sequences" in paths
    assert "/api/dm-sequences/device/sync" in paths
    assert "/api/device/collect-report" in paths
