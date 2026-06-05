from fastapi.testclient import TestClient

from app.db_models import ProviderCostReservation, ProviderStageTask
from app.main import app
from tests.video_production_control_plane_helpers import linked_segment_context


client = TestClient(app)


def _stage_task(db, ctx, index: int, *, status: str = "submitted"):
    task = ProviderStageTask(
        run_id=ctx["run"].id,
        plan_id=ctx["plan"].id,
        target_type="production_segment",
        target_id=ctx["segment"].id,
        stage="image_generation",
        provider="pixelle",
        model_name="seedance",
        request_hash=f"hash-{index}",
        idempotency_key=f"{ctx['plan'].id}:seg-{index}:image:v1",
        status=status,
        provider_task_id=f"provider-task-{index}",
    )
    db.add(task)
    db.flush()
    db.add(ProviderCostReservation(
        plan_id=ctx["plan"].id,
        provider_stage_task_id=task.id,
        status="submitted",
        estimated_cost=0.1,
        reserved_cost=0.1,
    ))
    return task


def test_provider_stage_tasks_are_bounded_and_include_cost_reservation(db):
    ctx = linked_segment_context(db)
    _stage_task(db, ctx, 1)
    for index in range(2, 122):
        _stage_task(db, ctx, index, status="sync_required")
    db.commit()

    resp = client.get(f"/api/video-production/runs/{ctx['run'].id}/provider-stage-tasks", params={"page_size": 500})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] == 121
    assert body["page_size"] == 100
    assert len(body["tasks"]) == 100
    returned = body["tasks"][0]
    assert returned["provider_task_id"].startswith("provider-task-")
    assert returned["cost_reservation"]["status"] == "submitted"


def test_provider_stage_tasks_support_stage_and_status_filters(db):
    ctx = linked_segment_context(db)
    _stage_task(db, ctx, 1, status="submitted")
    _stage_task(db, ctx, 2, status="sync_required")
    db.commit()

    resp = client.get(
        f"/api/video-production/runs/{ctx['run'].id}/provider-stage-tasks",
        params={"stage": "image_generation", "status": "sync_required"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["tasks"][0]["status"] == "sync_required"
