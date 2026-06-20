import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_ROOT = REPO_ROOT / "server/app/domains"

EXPECTED_DOMAIN_SERVICE_IMPORTS = {
    ("server/app/domains/agency_operations/agency_backtrack_policy.py", "production_queue_service"),
    ("server/app/domains/agency_operations/agency_multimodal_review.py", "agency_orchestrator"),
    ("server/app/domains/agency_operations/agency_persistence.py", "agency_creative_patch_service"),
    ("server/app/domains/agency_operations/agency_router.py", "agency_creative_patch_service"),
    ("server/app/domains/ai_text_artifacts/ai_text_artifact_service.py", "ai_generator"),
    ("server/app/domains/ai_video_series/read_models.py", "agency_console"),
    ("server/app/domains/ai_video_series/router.py", "production_run_service"),
    ("server/app/domains/ai_video_series/story_generator_expert.py", "agency_runtime"),
    ("server/app/domains/ai_video_series/story_planning.py", "production_queue_service"),
    ("server/app/domains/ai_video_series/style_lock.py", "agency_orchestrator"),
    ("server/app/domains/ai_video_series/style_lock.py", "ai_generator"),
    ("server/app/domains/ai_video_series/style_lock.py", "production_queue_service"),
    ("server/app/domains/ai_video_series/style_lock.py", "video_agency_team"),
    ("server/app/domains/content_collection/collection_reports.py", "ai_generator"),
    ("server/app/domains/content_collection/content_service.py", "ai_generator"),
    ("server/app/domains/content_collection/mutations.py", "ai_generator"),
    ("server/app/domains/creative_library/asset_ai_rewrite_service.py", "ai_generator"),
    ("server/app/domains/creative_library/characters_router.py", "ai_generator"),
    ("server/app/domains/creative_library/reference_asset_service.py", "image_creation_service"),
    ("server/app/domains/creative_library/scenes_router.py", "ai_generator"),
    ("server/app/domains/director_planning/director_router.py", "agency_orchestrator"),
    ("server/app/domains/director_planning/director_router.py", "ai_generator"),
    ("server/app/domains/director_planning/director_router.py", "video_agency_team"),
    ("server/app/domains/image_generation/image_ab_test_service.py", "image_creation_service"),
    ("server/app/domains/image_generation/image_asset_bridge_service.py", "image_creation_service"),
    ("server/app/domains/image_generation/image_creation_router.py", "image_creation_service"),
    ("server/app/domains/image_generation/image_selection_preview_service.py", "image_creation_service"),
    ("server/app/domains/prompt_management/prompt_templates_router.py", "ai_generator"),
    ("server/app/domains/script_pipeline/pipeline_router.py", "agency_orchestrator"),
    ("server/app/domains/script_pipeline/pipeline_router.py", "video_agency_team"),
    ("server/app/domains/script_pipeline/script_pipeline_service.py", "agency_orchestrator"),
    ("server/app/domains/script_pipeline/script_pipeline_service.py", "agency_runtime"),
    ("server/app/domains/storyboard_images/storyboard_image_service.py", "image_creation_service"),
    ("server/app/domains/video_production/mock_scale_scheduler_service.py", "production_queue_service"),
    ("server/app/domains/video_production/production_retry_service.py", "production_queue_service"),
    ("server/app/domains/video_production/provider_stage_executor.py", "production_queue_service"),
    ("server/app/domains/video_production/review_asset_edit_service.py", "image_creation_service"),
    ("server/app/domains/video_production/video_production_router.py", "one_sentence_video_service"),
    ("server/app/domains/video_production/video_production_router.py", "production_queue_service"),
    ("server/app/domains/video_production/video_production_router.py", "production_run_service"),
    ("server/app/domains/video_production/video_production_router.py", "production_worker_service"),
    ("server/app/domains/video_production/video_production_router.py", "video_production_readiness"),
    ("server/app/domains/video_production/video_production_router.py", "video_production_service"),
}


def test_domain_service_import_inventory_matches_allowlist():
    assert _domain_service_imports() == EXPECTED_DOMAIN_SERVICE_IMPORTS


def _domain_service_imports() -> set[tuple[str, str]]:
    imports: set[tuple[str, str]] = set()
    for path in DOMAIN_ROOT.rglob("*.py"):
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            imports.update(_service_imports_from_node(relative_path, node))
    return imports


def _service_imports_from_node(relative_path: str, node: ast.AST) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module == "app.services":
            for alias in node.names:
                found.add((relative_path, alias.name))
        elif module.startswith("app.services."):
            found.add((relative_path, module.split(".")[2]))
    elif isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.startswith("app.services."):
                found.add((relative_path, alias.name.split(".")[2]))
    return found
