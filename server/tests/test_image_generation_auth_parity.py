from fastapi.routing import APIRoute

from app.main import app


EXPECTED_IMAGE_GENERATION_HTTP_ROUTES = [
    ("/api/image-creation/uploads", ("POST",), "upload_image", "app.domains.image_generation.image_creation_router.upload_image", ("checker",)),
    ("/api/image-creation/pixelle-files/{file_path:path}", ("GET",), "pixelle_file", "app.domains.image_generation.image_creation_router.pixelle_file", ("get_db",)),
    ("/api/image-creation/tasks", ("POST",), "create_task", "app.domains.image_generation.image_creation_router.create_task", ("get_db", "checker")),
    ("/api/image-creation/tasks/{task_id}", ("GET",), "read_task", "app.domains.image_generation.image_creation_router.read_task", ("get_db", "checker")),
    ("/api/image-creation/tasks/{task_id}/sync", ("POST",), "sync_task", "app.domains.image_generation.image_creation_router.sync_task", ("get_db", "checker")),
    ("/api/image-creation/tasks/{task_id}/dispatch", ("POST",), "dispatch_task", "app.domains.image_generation.image_creation_router.dispatch_task", ("get_db", "checker")),
    ("/api/image-creation/assets", ("GET",), "assets", "app.domains.image_generation.image_creation_router.assets", ("get_db", "checker")),
    ("/api/image-creation/assets/{asset_id}/review", ("POST",), "review_asset", "app.domains.image_generation.image_creation_router.review_asset", ("get_db", "checker")),
    ("/api/image-creation/assets/{asset_id}/edit", ("POST",), "edit_asset", "app.domains.image_generation.image_creation_router.edit_asset", ("get_db", "checker")),
    ("/api/image-production/strategies/seed-defaults", ("POST",), "seed_defaults", "app.domains.image_generation.image_production_router.seed_defaults", ("get_db", "checker")),
    ("/api/image-production/strategies", ("GET",), "strategies", "app.domains.image_generation.image_production_router.strategies", ("get_db", "checker")),
    ("/api/image-production/strategies", ("POST",), "create", "app.domains.image_generation.image_production_router.create", ("get_db", "checker")),
    ("/api/image-production/strategies/metrics/refresh", ("POST",), "refresh_strategy_metrics", "app.domains.image_generation.image_production_router.refresh_strategy_metrics", ("get_db", "checker")),
    ("/api/image-production/selection-preview", ("POST",), "selection_preview", "app.domains.image_generation.image_production_router.selection_preview", ("get_db", "verify_admin_token")),
    ("/api/image-production/ab-tests/preview", ("POST",), "ab_preview", "app.domains.image_generation.image_production_router.ab_preview", ("get_db", "verify_admin_token")),
    ("/api/image-production/ab-tests", ("POST",), "ab_create", "app.domains.image_generation.image_production_router.ab_create", ("get_db", "checker")),
    ("/api/image-production/ab-tests/{group_id}", ("GET",), "ab_read", "app.domains.image_generation.image_production_router.ab_read", ("get_db", "checker")),
    ("/api/image-production/ab-tests/{group_id}/refresh", ("POST",), "ab_refresh", "app.domains.image_generation.image_production_router.ab_refresh", ("get_db", "checker")),
    ("/api/image-production/ab-tests/{group_id}/winner-recommendation", ("GET",), "ab_winner_recommendation", "app.domains.image_generation.image_production_router.ab_winner_recommendation", ("get_db", "checker")),
    ("/api/image-production/ab-tests/{group_id}/winner/{attempt_id}", ("POST",), "ab_winner", "app.domains.image_generation.image_production_router.ab_winner", ("get_db", "checker")),
    ("/api/image-production/ab-tests/{group_id}/no-winner", ("POST",), "ab_no_winner", "app.domains.image_generation.image_production_router.ab_no_winner", ("get_db", "checker")),
    ("/api/image-production/assets/{asset_id}/promote-to-video-asset", ("POST",), "promote_asset", "app.domains.image_generation.image_production_router.promote_asset", ("get_db", "checker")),
    ("/api/image-production/strategies/{strategy_id}/recommendations", ("GET",), "strategy_recommendations", "app.domains.image_generation.image_production_router.strategy_recommendations", ("get_db", "checker")),
    ("/api/image-production/strategies/{strategy_id}", ("GET",), "read", "app.domains.image_generation.image_production_router.read", ("get_db", "checker")),
    ("/api/image-production/strategies/{strategy_id}", ("PUT",), "update", "app.domains.image_generation.image_production_router.update", ("get_db", "checker")),
    ("/api/image-production/strategies/{strategy_id}/activate", ("POST",), "activate", "app.domains.image_generation.image_production_router.activate", ("get_db", "checker")),
    ("/api/image-production/strategies/{strategy_id}/archive", ("POST",), "archive", "app.domains.image_generation.image_production_router.archive", ("get_db", "checker")),
]


def test_image_generation_route_table_snapshot():
    assert _image_generation_http_routes() == EXPECTED_IMAGE_GENERATION_HTTP_ROUTES


def _image_generation_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and _is_image_generation_route(route.path):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes


def _is_image_generation_route(path):
    return path.startswith("/api/image-creation") or path.startswith("/api/image-production")
