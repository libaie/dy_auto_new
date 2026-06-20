from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_ROOT = REPO_ROOT / "server/app/services"

EXPECTED_NON_FACADE_SERVICE_FILES = {
    "agency_console.py",
    "agency_creative_patch_service.py",
    "agency_debate_audit.py",
    "agency_orchestrator.py",
    "agency_repair_executor.py",
    "agency_runtime.py",
    "ai_generator.py",
    "image_creation_service.py",
    "one_sentence_video_service.py",
    "production_queue_service.py",
    "production_run_service.py",
    "production_worker_service.py",
    "storyboard_image_service.py",
    "video_agency_team.py",
    "video_production_readiness.py",
}


def test_service_implementation_inventory_matches_allowlist():
    assert _non_facade_service_files() == EXPECTED_NON_FACADE_SERVICE_FILES


def _non_facade_service_files() -> set[str]:
    files = set()
    for path in SERVICES_ROOT.glob("*.py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "from app.domains" in text:
            continue
        files.add(path.name)
    return files
