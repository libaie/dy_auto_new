from fastapi.testclient import TestClient

from app.main import app


TASK_KEYS = {
    "id",
    "type",
    "account_id",
    "device_id",
    "params",
    "status",
    "created_at",
    "scheduled_at",
    "started_at",
    "completed_at",
    "result",
    "retry_count",
    "chain_instance_id",
    "step_order",
    "lease_id",
}


def test_task_create_list_and_detail_response_shapes():
    with TestClient(app) as client:
        created = client.post(
            "/api/tasks",
            json={
                "type": "nurture",
                "account_id": "acc-001",
                "params": {"duration": 15},
            },
        )
        listed = client.get("/api/tasks")
        detail = client.get(f"/api/tasks/{created.json()['id']}")

    assert created.status_code == 200
    assert set(created.json()) == TASK_KEYS
    assert created.json()["status"] == "pending"
    assert created.json()["params"]["duration"] == 15

    assert listed.status_code == 200
    assert set(listed.json()) == {"tasks", "total"}
    listed_task = next(task for task in listed.json()["tasks"] if task["id"] == created.json()["id"])
    assert set(listed_task) == TASK_KEYS

    assert detail.status_code == 200
    assert set(detail.json()) == TASK_KEYS
    assert detail.json()["id"] == created.json()["id"]


def test_task_batch_direct_create_delete_and_cancel_response_shapes():
    with TestClient(app) as client:
        batch = client.post(
            "/api/tasks/batch",
            json={
                "type": "nurture",
                "account_ids": ["acc-001"],
                "params": {"duration": 20},
            },
        )
        listed = client.get("/api/tasks", params={"type": "nurture"})
        task_id = listed.json()["tasks"][0]["id"]
        cancelled = client.post(f"/api/tasks/{task_id}/cancel")
        deleted = client.delete(f"/api/tasks/{task_id}")

    assert batch.status_code == 200
    assert batch.json() == {"created": 1, "mode": "direct"}

    assert cancelled.status_code == 200
    assert set(cancelled.json()) == TASK_KEYS
    assert cancelled.json()["status"] == "cancelled"

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "task_id": task_id}


def test_task_batch_delete_response_shape():
    with TestClient(app) as client:
        created = client.post(
            "/api/tasks",
            json={
                "type": "nurture",
                "account_id": "acc-001",
                "params": {"duration": 10},
            },
        )
        response = client.post("/api/tasks/batch-delete", json={"task_ids": [created.json()["id"]]})

    assert created.status_code == 200
    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
