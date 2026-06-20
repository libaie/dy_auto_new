import importlib
from pathlib import Path

from app.db_models import AgencyExpertInvocation, ProductionAuditEvent, ProductionPlan, Series, VideoProductionRun


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-repair-orchestrator-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-repair-orchestrator-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_repair_orchestrator.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_repair_orchestrator.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_repair_orchestrator_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_repair_orchestrator",
        "app.services.agency_repair_orchestrator",
        "app.domains.agency_operations.agency_repair_contracts",
        "app.domains.video_production.production_status",
        "app.domains.video_production.provider_cost_reservation_service",
        "enqueue_repair_tasks_for_invocation",
    ]:
        assert term in spec
        assert term in plan


def test_agency_repair_orchestrator_implementation_lives_in_agency_operations_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def enqueue_repair_tasks_for_invocation" in domain_text
    assert "app.domains.agency_operations.agency_repair_contracts" in domain_text
    assert "app.domains.video_production.production_status" in domain_text
    assert "app.domains.video_production.provider_cost_reservation_service" in domain_text
    assert "app.services.agency_repair_contracts" not in domain_text
    assert "app.services.production_status" not in domain_text
    assert "app.services.provider_cost_reservation_service" not in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "def enqueue_repair_tasks_for_invocation" not in legacy_text


def test_legacy_agency_repair_orchestrator_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.agency_operations.agency_repair_orchestrator")
    legacy = importlib.import_module("app.services.agency_repair_orchestrator")
    assert legacy is domain
    assert legacy.enqueue_repair_tasks_for_invocation is domain.enqueue_repair_tasks_for_invocation


def test_legacy_agency_repair_orchestrator_manual_required_behavior(db):
    legacy = importlib.import_module("app.services.agency_repair_orchestrator")
    series = Series(title="Repair", logline="Repair", genre="test")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=1.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id="episode-1",
        production_plan_id=plan.id,
        run_type="real_short_e2e",
        status="running",
        current_stage="style_lock",
    )
    db.add(run)
    db.flush()
    invocation = AgencyExpertInvocation(
        idempotency_key="repair-orchestrator-facade",
        series_id=series.id,
        run_id=run.id,
        production_plan_id=plan.id,
        stage="style_lock",
        expert_id="reviewer",
        role="reviewer",
        execution_status="completed",
        result_status="warning",
        output_summary_json={
            "repair_tasks": [{
                "type": "missing_character_reference",
                "stage": "style_lock",
                "target_type": "character",
                "target_id": "char-1",
                "auto_execute": True,
                "requires_paid_provider": True,
                "estimated_cost": 0.2,
            }],
        },
        source_repo="test",
        source_path="test.md",
        source_sha256="a" * 64,
    )
    db.add(invocation)
    db.flush()

    result = legacy.enqueue_repair_tasks_for_invocation(
        db,
        invocation,
        {
            "enabled": True,
            "max_rounds": 2,
            "budget_limit": 1,
            "allowed_stages": ["style_lock"],
            "allowed_types": ["missing_character_reference"],
        },
    )

    assert result["created"] == 0
    assert result["manual_required"] == 1
    db.flush()
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_manual_required").count() == 1


def test_agency_operations_readme_registers_repair_orchestrator_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_repair_orchestrator" in text
    assert "app.services.agency_repair_orchestrator" in text
