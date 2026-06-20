from fastapi.testclient import TestClient

from app.db.models import ProductionAuditEvent, ProductionJob
from app.main import app
from app.domains.video_production.production_status import JOB_BLOCKED, JOB_FAILED
from tests.test_agency_repair_loop import _series_plan_run

client = TestClient(app)


def test_repair_tasks_api_returns_retry_actions_and_no_fake_route(db):
    series, plan, run = _series_plan_run(db)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="manual",
        target_id="manual-1",
        stage="agency_auto_repair:manual_incomplete_repair_task",
        status=JOB_BLOCKED,
        idempotency_key="repair:api:no-route",
        blocked_reason="缺少可执行结论，需要人工确认",
    )
    db.add(job)
    db.flush()
    db.add(ProductionAuditEvent(
        event_type="agency_repair_task_created",
        run_id=run.id,
        production_plan_id=plan.id,
        payload_json={"job_id": job.id, "repair_task": {"type": "manual_incomplete_repair_task", "reason": "缺少可执行结论，需要人工确认"}},
    ))
    db.commit()

    response = client.get(f"/api/agency/repair-tasks?series_id={series.id}")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["repair_route"] is None
    assert item["retry_actions"]["primary_label"] == "去处理"
    assert item["retry_actions"]["manual_action_enabled"] is False


def test_repair_tasks_api_filters_jobs_by_run_id_before_summary_and_paging(db):
    series, plan, run = _series_plan_run(db)
    other_run = type(run)(
        series_id=series.id,
        episode_id="episode-other",
        production_plan_id=plan.id,
        run_type="real_short_e2e",
        status="image_human_review_required",
        current_stage="image_review",
    )
    db.add(other_run)
    db.flush()
    current_job = ProductionJob(
        plan_id=plan.id,
        target_type="manual",
        target_id="manual-current",
        stage="agency_auto_repair:manual_current",
        status=JOB_BLOCKED,
        idempotency_key="repair:api:current-run",
    )
    other_job = ProductionJob(
        plan_id=plan.id,
        target_type="manual",
        target_id="manual-other",
        stage="agency_auto_repair:manual_other",
        status=JOB_BLOCKED,
        idempotency_key="repair:api:other-run",
    )
    db.add_all([current_job, other_job])
    db.flush()
    db.add_all([
        ProductionAuditEvent(
            event_type="agency_repair_task_created",
            run_id=run.id,
            production_plan_id=plan.id,
            payload_json={"job_id": current_job.id, "repair_task": {"type": "manual_current", "reason": "current run"}},
        ),
        ProductionAuditEvent(
            event_type="agency_repair_task_created",
            run_id=other_run.id,
            production_plan_id=plan.id,
            payload_json={"job_id": other_job.id, "repair_task": {"type": "manual_other", "reason": "other run"}},
        ),
    ])
    db.commit()

    response = client.get(f"/api/agency/repair-tasks?series_id={series.id}&run_id={run.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["summary"]["total"] == 1
    assert [item["id"] for item in data["items"]] == [current_job.id]


def test_free_repair_retry_does_not_bypass_policy_allowed_types(db):
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 0,
        "allowed_stages": ["storyboard"],
        "allowed_types": ["storyboard_missing_references"],
        "requires_human_gate_after_repair": True,
    }
    _, plan, run = _series_plan_run(db, policy=policy)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="scene",
        target_id="scene-1",
        stage="agency_auto_repair:missing_scene_reference",
        status=JOB_FAILED,
        idempotency_key="repair:api:free-disallowed-type",
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
                "type": "missing_scene_reference",
                "stage": "storyboard",
                "target_type": "scene",
                "target_id": "scene-1",
                "requires_paid_provider": False,
                "round": 1,
                "reason": "场景缺少参考图",
            },
        },
    ))
    db.commit()

    response = client.post(f"/api/agency/repair-tasks/{job.id}/retry")

    assert response.status_code == 409
    db.refresh(job)
    assert job.status == JOB_FAILED


def test_repair_retry_uses_backend_retry_history_for_round_limit(db):
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 0,
        "allowed_stages": ["storyboard"],
        "allowed_types": ["storyboard_missing_references"],
        "requires_human_gate_after_repair": True,
    }
    _, plan, run = _series_plan_run(db, policy=policy)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="episode",
        target_id="episode-1",
        stage="agency_auto_repair:storyboard_missing_references",
        status=JOB_FAILED,
        idempotency_key="repair:api:round-limit",
    )
    db.add(job)
    db.flush()
    repair_task = {
        "type": "storyboard_missing_references",
        "stage": "storyboard",
        "target_type": "episode",
        "target_id": "episode-1",
        "requires_paid_provider": False,
        "round": 1,
        "reason": "分镜缺少参考图",
    }
    db.add_all([
        ProductionAuditEvent(
            event_type="agency_repair_task_created",
            run_id=run.id,
            production_plan_id=plan.id,
            payload_json={"job_id": job.id, "repair_task": repair_task},
        ),
        ProductionAuditEvent(
            event_type="agency_repair_retry_requested",
            run_id=run.id,
            production_plan_id=plan.id,
            payload_json={"job_id": job.id},
        ),
    ])
    db.commit()

    response = client.post(f"/api/agency/repair-tasks/{job.id}/retry")

    assert response.status_code == 409
    assert "轮数" in response.json()["detail"]
    db.refresh(job)
    assert job.status == JOB_FAILED
