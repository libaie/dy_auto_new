import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-plan-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-plan-service-domain-plan.md"
DOMAIN_PLAN_PATH = REPO_ROOT / "server/app/domains/video_production/production_plan_service.py"
LEGACY_PLAN_PATH = REPO_ROOT / "server/app/services/production_plan_service.py"
DIRECTOR_ROUTER_PATH = REPO_ROOT / "server/app/domains/director_planning/director_router.py"
DIRECTOR_README_PATH = REPO_ROOT / "server/app/domains/director_planning/README.md"
DIRECTOR_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-director-planning-domain-design.md"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_plan_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_plan_service",
        "app.services.production_plan_service",
        "create_episode_production_plan",
        "ensure_shot_segments",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_plan_service_domain_file_exists():
    assert DOMAIN_PLAN_PATH.exists()


def test_legacy_video_production_plan_service_is_thin_facade():
    text = LEGACY_PLAN_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def create_episode_production_plan" not in text
    assert "def ensure_shot_segments" not in text
    assert _line_count(LEGACY_PLAN_PATH) <= 20


def test_legacy_video_production_plan_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_plan_service")
        domain = importlib.import_module("app.domains.video_production.production_plan_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production plan service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.create_episode_production_plan is domain.create_episode_production_plan
    assert legacy.ensure_episode_production_plan is domain.ensure_episode_production_plan
    assert legacy.ensure_shot_segments is domain.ensure_shot_segments
    assert legacy._reference_roles is domain._reference_roles


def test_video_production_plan_service_imports_domain_status_contract():
    text = DOMAIN_PLAN_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_status" in text
    assert "app.services.production_status" not in text


def test_director_planning_router_imports_domain_plan_service():
    text = DIRECTOR_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_plan_service" in text
    assert "app.services.production_plan_service" not in text


def test_director_planning_readme_names_domain_plan_service_boundary():
    text = DIRECTOR_README_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_plan_service" in text
    assert "app.services.production_plan_service" not in text


def test_director_planning_spec_names_domain_plan_service_boundary():
    text = DIRECTOR_SPEC_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_plan_service" in text
    assert "app.services.production_plan_service" not in text


def test_video_production_readme_registers_plan_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_plan_service" in text
    assert "app.domains.video_production.production_plan_service" in text
    assert 'rg "app\\.services\\.production_plan_service" server/app server/tests' in text
    assert "create_episode_production_plan" in text
    assert "ensure_shot_segments" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
