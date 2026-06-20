import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_ROOT = REPO_ROOT / "server/app/services"
DOMAINS_ROOT = REPO_ROOT / "server/app/domains"

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

EXPECTED_MIXED_FACADE_SERVICE_FILES = {
    "video_production_service.py",
}

EXPECTED_SERVICE_DOMAIN_TARGETS = {
    "agency_console.py": "agency_operations",
    "agency_creative_patch_service.py": "agency_operations",
    "agency_debate_audit.py": "agency_operations",
    "agency_orchestrator.py": "agency_operations",
    "agency_repair_executor.py": "agency_operations",
    "agency_runtime.py": "agency_operations",
    "ai_generator.py": "model_configuration",
    "image_creation_service.py": "image_generation",
    "one_sentence_video_service.py": "video_production",
    "production_queue_service.py": "video_production",
    "production_run_service.py": "video_production",
    "production_worker_service.py": "video_production",
    "storyboard_image_service.py": "storyboard_images",
    "video_agency_team.py": "agency_operations",
    "video_production_readiness.py": "video_production",
}


def test_service_implementation_inventory_matches_allowlist():
    assert _non_facade_service_files() == EXPECTED_NON_FACADE_SERVICE_FILES


def test_mixed_facade_implementation_inventory_matches_allowlist():
    assert _mixed_facade_implementation_files() == EXPECTED_MIXED_FACADE_SERVICE_FILES


def test_service_implementation_files_have_target_domains():
    assert set(EXPECTED_SERVICE_DOMAIN_TARGETS) == EXPECTED_NON_FACADE_SERVICE_FILES
    assert all(EXPECTED_SERVICE_DOMAIN_TARGETS.values())


def test_service_implementation_targets_are_existing_domains():
    domain_names = {
        path.name
        for path in DOMAINS_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    assert set(EXPECTED_SERVICE_DOMAIN_TARGETS.values()) <= domain_names


def _non_facade_service_files() -> set[str]:
    files = set()
    for path in SERVICES_ROOT.glob("*.py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if _imports_domains(text):
            continue
        files.add(path.name)
    return files


def _mixed_facade_implementation_files() -> set[str]:
    files = set()
    for path in SERVICES_ROOT.glob("*.py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if not _imports_domains(text):
            continue
        tree = ast.parse(text)
        has_top_level_definition = any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            for node in tree.body
        )
        if has_top_level_definition:
            files.add(path.name)
    return files


def _imports_domains(text: str) -> bool:
    return "from app.domains" in text or "import app.domains" in text
