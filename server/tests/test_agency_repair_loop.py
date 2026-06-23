from fastapi.testclient import TestClient

from app.db.models import AgencyExpertInvocation, Character, Episode, ProductionAuditEvent, ProductionJob, ProductionPlan, Series, VideoProductionRun
from app.main import app
from app.domains.agency_operations.agency_repair_classifier import classify_repair_tasks
from app.domains.agency_operations.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation
from app.domains.video_production.production_status import JOB_BLOCKED, JOB_COMPLETED, JOB_FAILED, JOB_QUEUED
from app.domains.video_production.production_worker_service import run_real_worker_step

client = TestClient(app)


def _series_plan_run(db, *, policy=None, budget_limit=5.0):
    series = Series(title="老李控糖", logline="控糖健康短剧", genre="health")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="第一集", status="storyboard_ready")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=budget_limit, current_cost=0.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        run_type="real_short_e2e",
        status="running",
        current_stage="style_lock",
        model_trace_json={"auto_repair_policy": policy or {}},
    )
    db.add(run)
    db.flush()
    return series, plan, run


def _invocation(db, series, plan, run, repair_task):
    row = AgencyExpertInvocation(
        idempotency_key=f"repair-invocation:{repair_task['type']}:{repair_task.get('target_id') or 'none'}",
        series_id=series.id,
        run_id=run.id,
        production_plan_id=plan.id,
        stage=repair_task.get("stage", "style_lock"),
        expert_id="style_lock_quality_reviewer",
        role="reviewer",
        execution_status="completed",
        result_status="warning",
        output_summary_json={"repair_tasks": [repair_task]},
        source_repo="test",
        source_path="test.md",
        source_sha256="a" * 64,
    )
    db.add(row)
    db.flush()
    return row


def test_classifier_creates_readable_manual_fallback_for_malformed_output():
    result = classify_repair_tasks({"summary": "已记录审查发现"}, stage="style_lock", series_id="series-1")

    assert len(result.repair_tasks) == 1
    assert result.repair_tasks[0].reason == "专家审查结果缺少可执行结论，需要人工确认"
    assert result.repair_tasks[0].auto_execute is False

    result = classify_repair_tasks(
        {"repair_tasks": [{"reason": "閸樻槒顫楅懝鑼剁カ娴溠喫夐崣鍌濃偓鍐ㄦ禈"}]},
        stage="style_lock",
        series_id="series-1",
    )

    assert result.repair_tasks[0].reason == "专家审查结果缺少可执行结论，需要人工确认"
    assert result.repair_tasks[0].auto_execute is False


def test_orchestrator_enqueues_free_repair_without_internal_commit(db):
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 0,
        "allowed_stages": ["storyboard"],
        "allowed_types": ["storyboard_missing_references"],
        "requires_human_gate_after_repair": True,
    }
    series, plan, run = _series_plan_run(db, policy=policy)
    invocation = _invocation(db, series, plan, run, {
        "type": "storyboard_missing_references",
        "stage": "storyboard",
        "target_type": "episode",
        "target_id": "episode-1",
        "auto_execute": True,
        "requires_paid_provider": False,
        "reason": "分镜缺少参考图",
        "expected_result": "补齐引用后复审",
    })

    result = enqueue_repair_tasks_for_invocation(db, invocation, policy)
    db.commit()

    assert result["created"] == 1
    job = db.query(ProductionJob).filter(ProductionJob.stage == "agency_auto_repair:storyboard_missing_references").one()
    assert job.status == JOB_QUEUED
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_task_created").count() == 1


def test_paid_reference_repair_becomes_manual_when_cost_path_is_not_safe(db):
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 1.0,
        "allowed_stages": ["style_lock"],
        "allowed_types": ["missing_character_reference"],
        "requires_human_gate_after_repair": True,
    }
    series, plan, run = _series_plan_run(db, policy=policy)
    character = Character(name="老李", role_type="protagonist", gender="male")
    db.add(character)
    db.flush()
    invocation = _invocation(db, series, plan, run, {
        "type": "missing_character_reference",
        "stage": "style_lock",
        "target_type": "character",
        "target_id": character.id,
        "auto_execute": True,
        "requires_paid_provider": True,
        "estimated_cost": 0.2,
        "reason": "角色缺少侧面参考图",
    })

    result = enqueue_repair_tasks_for_invocation(db, invocation, policy)
    db.commit()

    assert result["manual_required"] == 1
    assert db.query(ProductionJob).count() == 0


def test_repair_tasks_api_projection_does_not_default_missing_route_to_root(db):
    series, plan, run = _series_plan_run(db)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="character",
        target_id="char-1",
        stage="agency_auto_repair:manual_incomplete_repair_task",
        status=JOB_BLOCKED,
        idempotency_key="repair:no-route",
        blocked_reason="缺少可执行结论，需要人工确认",
    )
    db.add(job)
    db.flush()
    db.add(ProductionAuditEvent(
        event_type="agency_repair_task_created",
        run_id=run.id,
        production_plan_id=plan.id,
        payload_json={"job_id": job.id, "repair_task": {"reason": "缺少可执行结论，需要人工确认", "repair_action_label": "联系人工处理"}},
    ))
    db.commit()

    response = client.get(f"/api/agency/repair-tasks?series_id={series.id}")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["repair_route"] is None
    assert item["retry_actions"]["manual_action_enabled"] is False
    assert item["retry_actions"]["primary_label"] == "去处理"


def test_authorize_paid_repair_retry_does_not_bypass_allowed_types(db):
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 5.0,
        "allowed_stages": ["style_lock"],
        "allowed_types": ["missing_scene_reference"],
        "requires_human_gate_after_repair": True,
    }
    series, plan, run = _series_plan_run(db, policy=policy)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="character",
        target_id="char-1",
        stage="agency_auto_repair:missing_character_reference",
        status=JOB_FAILED,
        idempotency_key="repair:authorize-disallowed-type",
        blocked_reason="自动返修预算不足，需要人工确认是否继续付费返修",
    )
    db.add(job)
    db.flush()
    db.add(ProductionAuditEvent(
        event_type="agency_repair_task_created",
        run_id=run.id,
        production_plan_id=plan.id,
        payload_json={
            "job_id": job.id,
            "repair_task": {
                "type": "missing_character_reference",
                "stage": "style_lock",
                "target_type": "character",
                "target_id": "char-1",
                "requires_paid_provider": True,
                "estimated_cost": 0.2,
                "round": 1,
                "reason": "角色缺少侧面参考图",
                "repair_action_label": "去角色资产补参考图",
                "repair_route": "/characters/char-1",
            },
        },
    ))
    db.commit()

    response = client.post(
        f"/api/agency/repair-tasks/{job.id}/authorize-retry",
        json={"reason": "确认继续付费补齐参考图", "confirmed_budget_delta": 1.0},
    )

    assert response.status_code == 409
    db.refresh(job)
    assert job.status == JOB_FAILED


def test_worker_dispatches_agency_auto_repair_job(db):
    series, plan, run = _series_plan_run(db)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="episode",
        target_id=run.episode_id,
        stage="agency_auto_repair:storyboard_missing_references",
        status=JOB_QUEUED,
        idempotency_key="repair:worker",
    )
    db.add(job)
    db.commit()

    result = run_real_worker_step(db, run.id, lease_id="repair-worker", batch_size=1)

    db.refresh(job)
    assert result["processed"] == 1
    assert job.status == JOB_COMPLETED
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_recheck_required").count() == 1
