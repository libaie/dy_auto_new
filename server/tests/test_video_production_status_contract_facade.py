import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-status-contract-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-status-contract-domain-plan.md"
DOMAIN_STATUS_PATH = REPO_ROOT / "server/app/domains/video_production/production_status.py"
LEGACY_STATUS_PATH = REPO_ROOT / "server/app/services/production_status.py"
DOMAIN_COST_PATH = REPO_ROOT / "server/app/domains/video_production/production_cost_service.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_status_contract_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_status",
        "app.services.production_status",
        "PLAN_DRAFT",
        "JOB_QUEUED",
        "SEGMENT_IMAGE_QUEUED",
        "STAGE_IMAGE_GENERATION",
        "CONTINUITY_NARRATIVE_CUT",
        "REFERENCE_CHARACTER_ANCHOR",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_status_contract_domain_file_exists():
    assert DOMAIN_STATUS_PATH.exists()


def test_legacy_video_production_status_contract_is_thin_facade():
    text = LEGACY_STATUS_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "PLAN_DRAFT =" not in text
    assert "JOB_QUEUED =" not in text
    assert "SEGMENT_IMAGE_QUEUED =" not in text
    assert "REFERENCE_CHARACTER_ANCHOR =" not in text
    assert _line_count(LEGACY_STATUS_PATH) <= 20


def test_legacy_video_production_status_contract_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_status")
        domain = importlib.import_module("app.domains.video_production.production_status")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production status domain import failed: {exc}")

    assert legacy is domain
    for name in [
        "PLAN_DRAFT",
        "PLAN_BLOCKED",
        "JOB_QUEUED",
        "JOB_LEASED",
        "JOB_COMPLETED",
        "SEGMENT_IMAGE_QUEUED",
        "SEGMENT_SUPERSEDED",
        "STAGE_IMAGE_GENERATION",
        "CONTINUITY_NARRATIVE_CUT",
        "REFERENCE_CHARACTER_ANCHOR",
    ]:
        assert getattr(legacy, name) is getattr(domain, name)


def test_video_production_cost_service_imports_domain_status_contract():
    text = DOMAIN_COST_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_status" in text
    assert "app.services.production_status" not in text


def test_video_production_readme_registers_status_contract_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_status" in text
    assert "app.domains.video_production.production_status" in text
    assert 'rg "app\\.services\\.production_status" server/app server/tests' in text
    assert "approved cross-domain consumers" in text
    assert "JOB_QUEUED" in text
    assert "REFERENCE_CHARACTER_ANCHOR" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
