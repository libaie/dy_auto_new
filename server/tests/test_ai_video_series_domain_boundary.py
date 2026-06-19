import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ai_video_series_domain_package_imports():
    import app.domains.ai_video_series as domain

    assert domain.DOMAIN_NAME == "ai_video_series"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/series"


def test_legacy_series_router_stays_thin_after_migration():
    router_path = REPO_ROOT / "server/app/routers/series.py"

    assert router_path.exists()
    assert _line_count(router_path) <= 30


def test_domain_router_is_route_assembly_not_business_logic_home():
    domain_router_path = REPO_ROOT / "server/app/domains/ai_video_series/router.py"

    assert domain_router_path.exists()
    assert _line_count(domain_router_path) <= 400


def test_domain_non_router_modules_do_not_import_fastapi():
    module_paths = [
        "server/app/domains/ai_video_series/read_models.py",
        "server/app/domains/ai_video_series/artifacts.py",
        "server/app/domains/ai_video_series/story_planning.py",
        "server/app/domains/ai_video_series/style_lock.py",
    ]
    for module_path in module_paths:
        text = (REPO_ROOT / module_path).read_text(encoding="utf-8")
        assert "from fastapi" not in text
        assert "import fastapi" not in text
        assert "from starlette" not in text
        assert "import starlette" not in text
        assert "HTTPException" not in text


def test_services_do_not_reverse_import_ai_video_series_domain():
    service_root = REPO_ROOT / "server/app/services"
    offenders = []
    for path in service_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        if _imports_ai_video_series_domain(tree) and not _is_allowed_domain_facade(text):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []


def test_app_import_smoke_after_domain_skeleton():
    from app.main import app

    assert app is not None


def test_worker_modules_expose_patchable_dependency_points():
    from app.domains.ai_video_series import story_planning, style_lock

    assert hasattr(style_lock, "claim_next_job")
    assert hasattr(style_lock, "generate_reference_url")
    assert hasattr(style_lock, "AgencyOrchestrator")
    assert hasattr(story_planning, "claim_next_job")
    assert hasattr(story_planning, "generate_series_story_plan")


def _line_count(path: Path | str) -> int:
    resolved = path if isinstance(path, Path) else REPO_ROOT / path
    return len(resolved.read_text(encoding="utf-8").splitlines())


def _imports_ai_video_series_domain(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_ai_video_series_module(alias.name):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_ai_video_series_module(module):
                return True
            if module == "app.domains":
                names = {alias.name for alias in node.names}
                if "ai_video_series" in names or "*" in names:
                    return True
    return False


def _is_allowed_domain_facade(text: str) -> bool:
    return (
        "Compatibility facade" in text
        and "sys.modules[" in text
        and "app.domains.ai_video_series" in text
    )

def _is_ai_video_series_module(module_name: str) -> bool:
    return module_name == "app.domains.ai_video_series" or module_name.startswith(
        "app.domains.ai_video_series."
    )
