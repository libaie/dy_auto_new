from app.db.models import AgencyExpertInvocation, ProductionAuditEvent, ProductionJob, ProductionPlan, Series, VideoProductionRun
from app.domains.agency_operations.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation


def _context(db, policy):
    series = Series(title="老李控糖", logline="控糖系列", genre="health")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id="episode-1",
        production_plan_id=plan.id,
        run_type="real_short_e2e",
        status="running",
        current_stage="storyboard",
        model_trace_json={"auto_repair_policy": policy},
    )
    db.add(run)
    db.flush()
    return series, plan, run


def _invocation(db, series, plan, run, task):
    row = AgencyExpertInvocation(
        idempotency_key=f"repair-test:{task['type']}:{task.get('target_id')}",
        series_id=series.id,
        run_id=run.id,
        production_plan_id=plan.id,
        stage=task["stage"],
        expert_id="storyboard_quality_reviewer",
        role="reviewer",
        execution_status="completed",
        result_status="warning",
        output_summary_json={"repair_tasks": [task]},
        source_repo="test",
        source_path="test.md",
        source_sha256="a" * 64,
    )
    db.add(row)
    db.flush()
    return row


def test_enabled_policy_enqueues_free_deterministic_repair(db):
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 0,
        "allowed_stages": ["storyboard"],
        "allowed_types": ["storyboard_missing_references"],
    }
    series, plan, run = _context(db, policy)
    invocation = _invocation(db, series, plan, run, {
        "type": "storyboard_missing_references",
        "stage": "storyboard",
        "target_type": "episode",
        "target_id": "episode-1",
        "auto_execute": True,
        "requires_paid_provider": False,
        "reason": "分镜缺少参考",
    })

    result = enqueue_repair_tasks_for_invocation(db, invocation, policy)

    assert result["created"] == 1
    assert db.query(ProductionJob).filter(ProductionJob.stage == "agency_auto_repair:storyboard_missing_references").count() == 1


def test_paid_reference_repair_is_manual_when_cost_path_is_not_caller_owned(db):
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 1,
        "allowed_stages": ["style_lock"],
        "allowed_types": ["missing_character_reference"],
    }
    series, plan, run = _context(db, policy)
    invocation = _invocation(db, series, plan, run, {
        "type": "missing_character_reference",
        "stage": "style_lock",
        "target_type": "character",
        "target_id": "char-1",
        "auto_execute": True,
        "requires_paid_provider": True,
        "estimated_cost": 0.2,
        "reason": "角色缺少参考图",
    })

    result = enqueue_repair_tasks_for_invocation(db, invocation, policy)
    db.flush()

    assert result["created"] == 0
    assert result["manual_required"] == 1
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_manual_required").count() == 1
