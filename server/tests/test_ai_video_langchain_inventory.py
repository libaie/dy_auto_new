from pathlib import Path


DOMAINS = Path(__file__).resolve().parents[1] / "app/domains"
SCOPED_DIRS = [
    DOMAINS / "ai_video_series",
    DOMAINS / "agency_operations",
    DOMAINS / "director_planning",
    DOMAINS / "script_pipeline",
    DOMAINS / "video_production",
]
FORBIDDEN_TEXT = [
    "ai_generator.generate_custom(",
    "httpx.AsyncClient(",
    "chat/completions",
    '"/api/video/generate/async"',
    '"/api/video/task/',
]
BOUNDARY_TEXT = [
    "execute_provider_job_direct(",
    "ProviderStageExecutor(",
]
BOUNDARY_ALLOW = {
    ("ai_video_series/langchain_runtime/provider_tools.py", "execute_provider_job_direct("),
    ("video_production/production_worker_service.py", "execute_provider_job_direct("),
    ("video_production/production_worker_service.py", "ProviderStageExecutor("),
}


def _python_files():
    for directory in SCOPED_DIRS:
        yield from directory.rglob("*.py")


def _rel(path: Path) -> str:
    return path.relative_to(DOMAINS).as_posix()


def test_ai_video_ai_calls_go_through_langchain_runtime():
    violations = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_TEXT:
            if needle in text:
                violations.append(f"{_rel(path)} contains {needle}")

    assert violations == []


def test_provider_direct_execution_stays_behind_langchain_tools():
    violations = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        rel = _rel(path)
        for needle in BOUNDARY_TEXT:
            if needle in text and (rel, needle) not in BOUNDARY_ALLOW:
                violations.append(f"{rel} contains {needle}")

    assert violations == []
