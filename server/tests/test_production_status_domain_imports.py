import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-production-status-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-production-status-domain-imports-plan.md"
DOMAIN_IMPORT_FILES = [
    REPO_ROOT / "server/app/domains/ai_video_series/story_planning.py",
    REPO_ROOT / "server/app/domains/ai_video_series/style_lock.py",
    REPO_ROOT / "server/app/domains/agency_operations/agency_router.py",
    REPO_ROOT / "server/app/domains/creative_library/anchor_service.py",
]


def test_production_status_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.video_production.production_status",
        "app.services.production_status",
        "style_lock",
        "story_planning",
    ]:
        assert term in spec
        assert term in plan


def test_domain_modules_import_production_status_from_domain_path():
    for path in DOMAIN_IMPORT_FILES:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.video_production.production_status" in text
        assert "app.services.production_status" not in text


def test_legacy_production_status_facade_still_resolves_to_domain_module():
    legacy = importlib.import_module("app.services.production_status")
    domain = importlib.import_module("app.domains.video_production.production_status")
    assert legacy is domain
    assert legacy.JOB_QUEUED == domain.JOB_QUEUED
    assert legacy.REFERENCE_CHARACTER_ANCHOR == domain.REFERENCE_CHARACTER_ANCHOR
