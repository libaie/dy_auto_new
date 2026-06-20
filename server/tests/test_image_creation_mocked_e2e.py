from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import AIModel, ImageCreationAsset, ImageCreationTask
from app.main import app
from app.domains.system_configuration.crypto import encrypt


client = TestClient(app)


def _seed_image_generation_model(db):
    model = AIModel(
        name=f"image-generation-e2e-{uuid4().hex}",
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret"),
        model_name=f"mock-image-{uuid4().hex}",
        enabled=True,
        config_json={
            "scene_key": "image_generation",
            "capabilities": {"text_to_image": True, "text_to_image_set": True},
            "limits": {"max_output_images": 15, "max_reference_images": 14},
        },
    )
    db.add(model)
    db.commit()
    return model


def test_mocked_text_to_image_flow_approves_downstream_asset(db, monkeypatch):
    _seed_image_generation_model(db)
    submit_calls = []

    async def fake_submit(**kwargs):
        submit_calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-e2e-1"}

    async def fake_stage_task(db, stage_task_id):
        assert stage_task_id == "stage-e2e-1"
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "url": "http://example.test/e2e-output.png",
                "local_path": "outputs/e2e-output.png",
                "metadata": {"group_id": "e2e-group", "group_index": 0},
                "provider_task_id": "provider-e2e-asset",
            }],
        }

    async def fake_copy_external(url):
        assert url == "http://example.test/e2e-output.png"
        return {
            "url": "http://127.0.0.1:8000/static/image-creation/outputs/e2e-output.png",
            "local_path": "D:\\outputs\\e2e-output.png",
            "storage_path": "outputs/e2e-output.png",
            "checksum": "e2e-checksum",
            "size_bytes": 12,
            "mime_type": "image/png",
        }

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.submit_image_create", fake_submit)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service.get_stage_task", fake_stage_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service._copy_external_image", fake_copy_external)

    created = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "wide shot neon noodle shop",
        "count": 1,
        "idempotency_key": "mock-e2e-1",
        "destination_role": "image_to_video_input",
        "cost_confirmation": True,
    })

    assert created.status_code == 200
    task_id = created.json()["task"]["id"]
    assert created.json()["task"]["pixelle_task_id"] == "stage-e2e-1"
    assert submit_calls[0]["mode"] == "text_to_image"

    synced = client.post(f"/api/image-creation/tasks/{task_id}/sync")

    assert synced.status_code == 200
    assets = synced.json()["assets"]
    assert len(assets) == 1
    assert assets[0]["status"] == "review_pending"
    asset_id = assets[0]["id"]
    asset_version = assets[0]["version"]

    reviewed = client.post(f"/api/image-creation/assets/{asset_id}/review", json={"action": "approve", "asset_version": asset_version})

    assert reviewed.status_code == 200
    assert reviewed.json()["asset"]["status"] == "approved"

    selected = client.get("/api/image-creation/assets?status=approved&destination_role=image_to_video_input")

    assert selected.status_code == 200
    selected_assets = selected.json()["assets"]
    assert [asset["id"] for asset in selected_assets] == [asset_id]
    assert selected_assets[0]["destination_role"] == "image_to_video_input"


def test_review_pending_asset_does_not_appear_in_approved_downstream_selector(db):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="pending selector",
        status="completed",
        count=1,
        target_count=1,
        completed_count=1,
    )
    db.add(task)
    db.commit()
    pending_asset = ImageCreationAsset(
        task_id=task.id,
        asset_type="image",
        asset_kind="image",
        url="http://example.test/pending.png",
        status="review_pending",
        version=1,
        slot_key="pending-slot",
        destination_role="image_to_video_input",
        audit_status="pending",
        manual_review_status="pending",
        storage_status="persisted",
    )
    db.add(pending_asset)
    db.commit()

    resp = client.get("/api/image-creation/assets?status=approved&destination_role=image_to_video_input")

    assert resp.status_code == 200
    assert resp.json()["assets"] == []
    assert resp.json()["total"] == 0
