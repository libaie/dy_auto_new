import importlib

from fastapi.routing import APIRoute


EXPECTED_IMAGE_CREATION_ROUTES = [
    ("POST", "/api/image-creation/uploads", "upload_image"),
    ("GET", "/api/image-creation/pixelle-files/{file_path:path}", "pixelle_file"),
    ("POST", "/api/image-creation/tasks", "create_task"),
    ("GET", "/api/image-creation/tasks/{task_id}", "read_task"),
    ("POST", "/api/image-creation/tasks/{task_id}/sync", "sync_task"),
    ("POST", "/api/image-creation/tasks/{task_id}/dispatch", "dispatch_task"),
    ("GET", "/api/image-creation/assets", "assets"),
    ("POST", "/api/image-creation/assets/{asset_id}/review", "review_asset"),
    ("POST", "/api/image-creation/assets/{asset_id}/edit", "edit_asset"),
]


EXPECTED_IMAGE_PRODUCTION_ROUTES = [
    ("POST", "/api/image-production/strategies/seed-defaults", "seed_defaults"),
    ("GET", "/api/image-production/strategies", "strategies"),
    ("POST", "/api/image-production/strategies", "create"),
    ("POST", "/api/image-production/strategies/metrics/refresh", "refresh_strategy_metrics"),
    ("POST", "/api/image-production/selection-preview", "selection_preview"),
    ("POST", "/api/image-production/ab-tests/preview", "ab_preview"),
    ("POST", "/api/image-production/ab-tests", "ab_create"),
    ("GET", "/api/image-production/ab-tests/{group_id}", "ab_read"),
    ("POST", "/api/image-production/ab-tests/{group_id}/refresh", "ab_refresh"),
    ("GET", "/api/image-production/ab-tests/{group_id}/winner-recommendation", "ab_winner_recommendation"),
    ("POST", "/api/image-production/ab-tests/{group_id}/winner/{attempt_id}", "ab_winner"),
    ("POST", "/api/image-production/ab-tests/{group_id}/no-winner", "ab_no_winner"),
    ("POST", "/api/image-production/assets/{asset_id}/promote-to-video-asset", "promote_asset"),
    ("GET", "/api/image-production/strategies/{strategy_id}/recommendations", "strategy_recommendations"),
    ("GET", "/api/image-production/strategies/{strategy_id}", "read"),
    ("PUT", "/api/image-production/strategies/{strategy_id}", "update"),
    ("POST", "/api/image-production/strategies/{strategy_id}/activate", "activate"),
    ("POST", "/api/image-production/strategies/{strategy_id}/archive", "archive"),
]


def test_image_creation_legacy_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.image_creation")
    domain_router = importlib.import_module("app.domains.image_generation.image_creation_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_IMAGE_CREATION_ROUTES


def test_image_production_legacy_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.image_production")
    domain_router = importlib.import_module("app.domains.image_generation.image_production_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_IMAGE_PRODUCTION_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot
