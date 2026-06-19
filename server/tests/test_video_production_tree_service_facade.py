import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-tree-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-tree-service-domain-plan.md"
DOMAIN_TREE_PATH = REPO_ROOT / "server/app/domains/video_production/production_tree_service.py"
LEGACY_TREE_PATH = REPO_ROOT / "server/app/services/production_tree_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_tree_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_tree_service",
        "app.services.production_tree_service",
        "get_run_tree",
        "_segment_payload",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_tree_service_domain_file_exists():
    assert DOMAIN_TREE_PATH.exists()


def test_legacy_video_production_tree_service_is_thin_facade():
    text = LEGACY_TREE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def get_run_tree" not in text
    assert "def _segment_payload" not in text
    assert _line_count(LEGACY_TREE_PATH) <= 20


def test_legacy_video_production_tree_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_tree_service")
        domain = importlib.import_module("app.domains.video_production.production_tree_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production tree service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.get_run_tree is domain.get_run_tree
    assert legacy._segment_payload is domain._segment_payload


def test_video_production_router_imports_domain_tree_service():
    text = ROUTER_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_production.production_tree_service import get_run_tree" in text
    assert "from app.services.production_tree_service import get_run_tree" not in text


def test_video_production_tree_service_imports_domain_status_contract():
    text = DOMAIN_TREE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_status" in text
    assert "app.services.production_status" not in text


def test_video_production_readme_registers_tree_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_tree_service" in text
    assert "app.domains.video_production.production_tree_service" in text
    assert 'rg "app\\.services\\.production_tree_service" server/app server/tests' in text
    assert "get_run_tree" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
