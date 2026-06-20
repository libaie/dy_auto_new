import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-production-observability-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-production-observability-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/production_observability/production_observability_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/production_observability.py"
README_PATH = REPO_ROOT / "server/app/domains/production_observability/README.md"
CLEAN_DOMAIN_CALLERS = [
    REPO_ROOT / "server/app/domains/agency_operations/agency_router.py",
    REPO_ROOT / "server/app/domains/image_generation/image_ab_test_service.py",
    REPO_ROOT / "server/app/domains/image_generation/image_production_strategy_service.py",
    REPO_ROOT / "server/app/domains/video_production/production_gate_evaluator.py",
    REPO_ROOT / "server/app/domains/video_production/mock_scale_scheduler_service.py",
    REPO_ROOT / "server/app/domains/video_production/provider_stage_executor.py",
]


def test_production_observability_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.production_observability.production_observability_service",
        "app.services.production_observability",
        "_redact",
        "record_production_event",
    ]:
        assert term in spec
        assert term in plan


def test_production_observability_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_production_observability_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.production_observability" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def record_production_event" not in text
    assert "def _redact" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_production_observability_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_observability")
        domain = importlib.import_module("app.domains.production_observability.production_observability_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"production observability domain import failed: {exc}")

    assert legacy is domain
    assert legacy.record_production_event is domain.record_production_event
    assert legacy._normalize_key is domain._normalize_key
    assert legacy._redact is domain._redact
    assert legacy.SECRET_KEYS is domain.SECRET_KEYS


def test_related_video_production_specs_name_shared_observability_domain():
    spec_paths = [
        REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-gate-evaluator-domain-design.md",
        REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-mock-scale-scheduler-domain-design.md",
    ]

    for path in spec_paths:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.production_observability.production_observability_service" in text, path
        assert "app.services.production_observability" not in text, path


def test_clean_domain_callers_import_shared_observability_domain():
    for path in CLEAN_DOMAIN_CALLERS:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.production_observability.production_observability_service" in text, path
        assert "app.services.production_observability" not in text, path


def test_production_observability_readme_registers_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "production_observability_service.py" in text
    assert "record_production_event" in text
    assert "_normalize_key" in text
    assert "_redact" in text
    assert "app.services.production_observability" in text
    assert "app.domains.production_observability.production_observability_service" in text
    assert 'rg "app\\.services\\.production_observability" server/app server/tests' in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
