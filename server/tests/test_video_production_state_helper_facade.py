import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-state-helper-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-state-helper-domain-plan.md"
DOMAIN_STATE_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_state.py"
LEGACY_STATE_PATH = REPO_ROOT / "server/app/services/video_production_state.py"
REVIEW_SERVICE_PATH = REPO_ROOT / "server/app/domains/video_production/production_review_service.py"
AI_VIDEO_STATUS_PATH = REPO_ROOT / "server/app/domains/ai_video_series/status_read_model.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_state_helper_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.video_production_state",
        "app.services.video_production_state",
        "production_segment_frame_ids",
        "recompute_run_gate",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_state_helper_domain_file_exists():
    assert DOMAIN_STATE_PATH.exists()


def test_legacy_video_production_state_helper_is_thin_facade():
    text = LEGACY_STATE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "IMAGE_READY_STATUS =" not in text
    assert "def production_segment_frame_ids" not in text
    assert "def recompute_run_gate" not in text
    assert _line_count(LEGACY_STATE_PATH) <= 20


def test_legacy_video_production_state_helper_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.video_production_state")
        domain = importlib.import_module("app.domains.video_production.video_production_state")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production state helper domain import failed: {exc}")

    assert legacy is domain
    assert legacy.IMAGE_READY_STATUS is domain.IMAGE_READY_STATUS
    assert legacy.VIDEO_READY_STATUS is domain.VIDEO_READY_STATUS
    assert legacy.production_segment_frame_ids is domain.production_segment_frame_ids
    assert legacy.recompute_run_gate is domain.recompute_run_gate


def test_clean_domain_callers_import_domain_state_helper():
    review_service = REVIEW_SERVICE_PATH.read_text(encoding="utf-8")
    ai_video_status = AI_VIDEO_STATUS_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.video_production_state" in review_service
    assert "app.domains.video_production.video_production_state" in ai_video_status
    assert "app.services.video_production_state" not in review_service
    assert "app.services.video_production_state" not in ai_video_status


def test_video_production_readme_registers_state_helper_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.video_production_state" in text
    assert "app.domains.video_production.video_production_state" in text
    assert 'rg "app\\.services\\.video_production_state" server/app server/tests' in text
    assert "production_segment_frame_ids" in text
    assert "recompute_run_gate" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
