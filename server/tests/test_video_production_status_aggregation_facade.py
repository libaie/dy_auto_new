import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-status-aggregation-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-status-aggregation-domain-plan.md"
DOMAIN_AGGREGATION_PATH = REPO_ROOT / "server/app/domains/video_production/production_status_aggregation.py"
LEGACY_AGGREGATION_PATH = REPO_ROOT / "server/app/services/production_status_aggregation.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_status_aggregation_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_status_aggregation",
        "app.services.production_status_aggregation",
        "_parent_status",
        "recompute_from_segment",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_status_aggregation_domain_file_exists():
    assert DOMAIN_AGGREGATION_PATH.exists()


def test_legacy_video_production_status_aggregation_is_thin_facade():
    text = LEGACY_AGGREGATION_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def _parent_status" not in text
    assert "def recompute_from_segment" not in text
    assert _line_count(LEGACY_AGGREGATION_PATH) <= 20


def test_legacy_video_production_status_aggregation_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_status_aggregation")
        domain = importlib.import_module("app.domains.video_production.production_status_aggregation")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production status aggregation domain import failed: {exc}")

    assert legacy is domain
    assert legacy._parent_status is domain._parent_status
    assert legacy.recompute_from_segment is domain.recompute_from_segment


def test_video_production_readme_registers_status_aggregation_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_status_aggregation" in text
    assert "app.domains.video_production.production_status_aggregation" in text
    assert 'rg "app\\.services\\.production_status_aggregation" server/app server/tests' in text
    assert "recompute_from_segment" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
