from fastapi.testclient import TestClient

from app.db_models import ProductionAuditEvent, ProductionJob
from app.main import app
from app.services.production_status import JOB_BLOCKED
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
