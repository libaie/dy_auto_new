from fastapi.testclient import TestClient

from app.db.models import AgencyExpertInvocation, ProductionJob
from app.main import app
from app.domains.agency_operations.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation
from tests.test_agency_repair_loop import _series_plan_run

client = TestClient(app)


def test_expert_finding_creates_repair_job_and_visible_audit(db):
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 0,
        "allowed_stages": ["storyboard"],
        "allowed_types": ["storyboard_missing_references"],
        "requires_human_gate_after_repair": True,
    }
    series, plan, run = _series_plan_run(db, policy=policy)
    invocation = AgencyExpertInvocation(
        idempotency_key="repair:e2e:invocation",
        series_id=series.id,
        run_id=run.id,
        production_plan_id=plan.id,
        stage="storyboard",
        expert_id="storyboard_quality_reviewer",
        role="reviewer",
        execution_status="completed",
        result_status="warning",
        output_summary_json={
            "repair_tasks": [{
                "type": "storyboard_missing_references",
                "stage": "storyboard",
                "target_type": "episode",
                "target_id": "episode-1",
                "auto_execute": True,
                "requires_paid_provider": False,
                "reason": "分镜缺少角色参考图",
                "expected_result": "补齐后重新进入审查",
                "repair_action_label": "去系列详情补分镜参考",
            }],
        },
        source_repo="test",
        source_path="test.md",
        source_sha256="a" * 64,
    )
    db.add(invocation)
    db.flush()

    result = enqueue_repair_tasks_for_invocation(db, invocation, policy)
    db.commit()

    assert result["created"] == 1
    assert db.query(ProductionJob).filter(ProductionJob.stage.like("agency_auto_repair%")).count() == 1
    response = client.get(f"/api/agency/repair-tasks?series_id={series.id}")
    assert response.status_code == 200
    assert response.json()["summary"]["total"] == 1
    assert response.json()["items"][0]["reason"] == "分镜缺少角色参考图"
