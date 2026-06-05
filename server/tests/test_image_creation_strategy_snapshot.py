from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db_models import AIModel, ImageCreationTask, ImageCreationAsset, ImageProductionCostEvent, ImageProductionPolicyVersion
from app.deps import verify_admin_token
from app.main import app
from app.services.crypto import encrypt
from app.services.image_creation_service import create_image_task, _redact_provider_error
from app.services.image_production_strategy_service import create_strategy
from app.services.image_selection_preview_service import create_selection_preview


client = TestClient(app)


def _seed_model(db, *, name_prefix="snapshot-model", capabilities=None, config_extra=None):
    config = {
        "scene_key": "image_generation",
        "scene_keys": ["image_generation"],
        "capabilities": capabilities or {"text_to_image": True},
        "provider_options_schema": {"watermark": {"type": "boolean"}},
        "config_version": 7,
        "secret_config_key": "must-not-leak",
    }
    if config_extra:
        config.update(config_extra)
    model = AIModel(
        name=f"{name_prefix}-{uuid4().hex}",
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret-key"),
        model_name=f"mock-{uuid4().hex}",
        enabled=True,
        config_json=config,
    )
    db.add(model)
    db.commit()
    return model


def _strategy(db, model, **overrides):
    payload = {
        "slug": f"snapshot-strategy-{uuid4().hex}",
        "name": "Snapshot Strategy",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image"],
        "default_model_id": model.id,
        "common_parameters": {"size": "1024x1024"},
        "provider_options": {"watermark": True},
    }
    payload.update(overrides)
    return create_strategy(db, payload)


def _policy(db, policy_type, snapshot):
    row = ImageProductionPolicyVersion(
        policy_type=policy_type,
        name=f"{policy_type}-creation-{uuid4().hex}",
        version=1,
        snapshot_json=snapshot,
        status="active",
    )
    db.add(row)
    db.commit()
    return row


def test_create_image_task_with_strategy_persists_snapshot(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "snapshot-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "cinematic first frame",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    body = resp.json()["task"]
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == body["id"]).first()
    assert task.user_id == "test-user-id"
    assert task.strategy_id == strategy.id
    assert task.strategy_version == strategy.version
    assert task.strategy_snapshot_json["slug"] == strategy.slug
    assert task.size == "1024x1024"
    assert task.provider_options_json == {"watermark": True}
    assert task.model_id == model.id
    assert task.selection_explanation_json["selected_model_id"] == model.id
    assert task.selection_explanation_json["resolved_capability_key"] == "text_to_image"
    assert "secret" not in str(task.model_trace_json).lower()
    assert body["strategy"]["id"] == strategy.id
    assert body["selection_explanation"]["selected_model_id"] == model.id


def test_create_image_task_without_strategy_still_works(db, monkeypatch):
    _seed_model(db)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "no-strategy-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "existing path",
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    body = resp.json()["task"]
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == body["id"]).first()
    assert task.strategy_id is None
    assert body["strategy"] is None


def test_create_image_task_requires_explicit_high_cost_confirmation(db, monkeypatch):
    model = _seed_model(db)
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2,
        "currency": "CNY",
        "confirmation_threshold": 1,
        "latency_seconds_per_image": 5,
    })
    strategy = _strategy(db, model, cost_policy_version_id=cost_policy.id)

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run without cost confirmation")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "expensive image",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
    })

    detail = resp.json()["detail"]
    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_COST_CONFIRMATION_REQUIRED"
    assert detail["details"]["cost_estimate"]["amount"] == 2
    assert detail["details"]["cost_estimate"]["requires_confirmation"] is True
    assert db.query(ImageCreationTask).count() == 0


def test_create_image_task_requires_fresh_preview_for_high_cost_confirmation(db, monkeypatch):
    model = _seed_model(db)
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2,
        "currency": "CNY",
        "confirmation_threshold": 1,
        "latency_seconds_per_image": 5,
    })
    strategy = _strategy(db, model, cost_policy_version_id=cost_policy.id)

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run without a matching cost preview")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "expensive confirmed without preview",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    detail = resp.json()["detail"]
    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_COST_CONFIRMATION_PREVIEW_REQUIRED"
    assert db.query(ImageCreationTask).count() == 0


def test_create_image_task_accepts_high_cost_confirmation_with_matching_preview(db, monkeypatch):
    model = _seed_model(db)
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2,
        "currency": "CNY",
        "confirmation_threshold": 1,
        "latency_seconds_per_image": 5,
    })
    strategy = _strategy(db, model, cost_policy_version_id=cost_policy.id)
    payload = {
        "mode": "text_to_image",
        "prompt": "expensive matching preview",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "size": "1024x1024",
        "response_format": "url",
        "provider_options": {"watermark": True},
    }
    preview = create_selection_preview(db, payload, user_id="test-user-id")

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "high-cost-preview-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        **payload,
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    assert resp.json()["task"]["prompt"] == "expensive matching preview"


@pytest.mark.parametrize(
    ("field", "changed_value"),
    [
        ("prompt", "changed expensive prompt"),
        ("size", "2048x2048"),
        ("response_format", "b64_json"),
    ],
)
def test_create_image_task_rejects_high_cost_confirmation_when_preview_request_changes(
    db,
    monkeypatch,
    field,
    changed_value,
):
    model = _seed_model(db)
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2,
        "currency": "CNY",
        "confirmation_threshold": 1,
        "latency_seconds_per_image": 5,
    })
    strategy = _strategy(db, model, cost_policy_version_id=cost_policy.id)
    preview_payload = {
        "mode": "text_to_image",
        "prompt": "expensive preview request",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "size": "1024x1024",
        "response_format": "url",
        "provider_options": {"watermark": True},
    }
    preview = create_selection_preview(db, preview_payload, user_id="test-user-id")

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for stale high-cost preview")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    create_payload = {**preview_payload, field: changed_value}
    resp = client.post("/api/image-creation/tasks", json={
        **create_payload,
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_SELECTION_PREVIEW_DRIFT"
    assert db.query(ImageCreationTask).count() == 0


def test_create_image_task_queues_when_capacity_full(db, monkeypatch):
    model = _seed_model(db)
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": True,
    })
    strategy = _strategy(db, model, capacity_policy_version_id=capacity_policy.id)
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        prompt="busy",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=model.id,
        capacity_lease_id="busy-lease",
    ))
    db.commit()

    async def fake_submit(**kwargs):
        raise AssertionError("queued task should not be submitted to Pixelle")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "wait in queue",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    body = resp.json()["task"]
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == body["id"]).first()
    assert resp.status_code == 200
    assert body["status"] == "queued"
    assert body["queue_job_id"] == task.queue_job_id
    assert body["queue_job_id"]
    assert body["capacity_lease_id"] is None
    assert body["pixelle_task_id"] is None
    assert body["capacity"]["admission_action"] == "queue"
    assert task.queue_job_id
    assert task.capacity_lease_id is None
    assert task.pixelle_task_id is None
    assert db.query(ImageProductionCostEvent).filter(ImageProductionCostEvent.task_id == task.id).count() == 1


def test_create_image_task_blocks_when_capacity_full_without_queue(db, monkeypatch):
    model = _seed_model(db)
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": False,
    })
    strategy = _strategy(db, model, capacity_policy_version_id=capacity_policy.id)
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        prompt="busy",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=model.id,
        capacity_lease_id="busy-lease",
    ))
    db.commit()

    async def fake_submit(**kwargs):
        raise AssertionError("blocked task should not be submitted to Pixelle")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "blocked by capacity",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    detail = resp.json()["detail"]
    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_CAPACITY_BLOCKED"
    assert detail["details"]["capacity"]["admission_action"] == "block"
    assert {action["type"] for action in detail["rescue_actions"]} == {"wait_for_capacity", "reduce_queue"}
    assert db.query(ImageCreationTask).filter(ImageCreationTask.prompt == "blocked by capacity").count() == 0


def test_dispatch_queued_image_task_submits_to_pixelle(db, monkeypatch):
    model = _seed_model(db)
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": True,
    })
    strategy = _strategy(db, model, capacity_policy_version_id=capacity_policy.id)
    busy = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        prompt="busy",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=model.id,
        capacity_lease_id="busy-lease",
    )
    db.add(busy)
    db.commit()

    async def fail_submit(**kwargs):
        raise AssertionError("create should queue without Pixelle")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fail_submit)
    create_resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "dispatch later",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })
    task_id = create_resp.json()["task"]["id"]
    busy.status = "completed"
    busy.capacity_lease_id = None
    db.commit()

    captured = {}

    async def fake_submit(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "stage_task_id": "dispatch-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post(f"/api/image-creation/tasks/{task_id}/dispatch")
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).first()

    assert resp.status_code == 200
    assert resp.json()["task"]["status"] == "running"
    assert resp.json()["task"]["pixelle_task_id"] == "dispatch-stage"
    assert resp.json()["task"]["queue_job_id"] is None
    assert resp.json()["task"]["capacity_lease_id"] == task.capacity_lease_id
    assert task.capacity_lease_id
    assert captured["external_task_id"] == task.id
    assert captured["model_config"]["model_id"] == model.id


def test_dispatch_queued_image_task_requires_saved_pixelle_payload(db):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="queued",
        prompt="missing payload",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=model.id,
        pixelle_payload_json={},
        queue_job_id=str(uuid4()),
    )
    db.add(task)
    db.commit()

    resp = client.post(f"/api/image-creation/tasks/{task.id}/dispatch")
    detail = resp.json()["detail"]

    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_QUEUE_PAYLOAD_MISSING"
    assert detail["affected_ids"] == [task.id]


def test_dispatch_queued_image_task_marks_failed_when_pixelle_submit_fails(db, monkeypatch):
    model = _seed_model(db)
    fallback = _seed_model(db, name_prefix="dispatch-fallback-model")
    strategy = _strategy(db, model)
    strategy.fallback_model_ids_json = [fallback.id]
    db.commit()
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="queued",
        prompt="dispatch failure",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_scene_key="image_generation",
        model_scene="image_generation",
        model_id=model.id,
        provider=model.provider,
        pixelle_payload_json={
            "external_task_id": "queued-external",
            "mode": "text_to_image",
            "capability_key": "text_to_image",
            "output_mode": "single",
            "prompt": "dispatch failure",
            "negative_prompt": "",
            "source_image_url": "",
            "reference_images": [],
            "count": 1,
            "size": "1024x1024",
            "output_format": "",
            "response_format": "",
            "provider_options": {"watermark": True},
            "context": {},
        },
        queue_job_id=str(uuid4()),
    )
    db.add(task)
    db.commit()

    async def fake_submit(**kwargs):
        raise RuntimeError("dispatch unavailable")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post(f"/api/image-creation/tasks/{task.id}/dispatch")
    detail = resp.json()["detail"]
    db.refresh(task)

    assert resp.status_code == 502
    assert detail["error_code"] == "PIXELLE_IMAGE_DISPATCH_FAILED"
    assert detail["affected_ids"] == [task.id]
    assert task.status == "failed"
    assert task.capacity_lease_id is None
    assert task.error_code == "PIXELLE_IMAGE_DISPATCH_FAILED"
    assert task.fallback_trace_json["error_code"] == "PIXELLE_IMAGE_DISPATCH_FAILED"
    assert task.fallback_trace_json["fallback_candidates"][0]["model_id"] == fallback.id


def test_create_image_task_rechecks_capacity_before_lease(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    calls = []

    def fake_capacity(db_arg, strategy_arg, model_id):
        calls.append(model_id)
        if len(calls) == 1:
            return {
                "status": "available",
                "admission_action": "submit_now",
                "active_count": 0,
                "queued_count": 0,
                "queue_depth": 0,
                "max_concurrent": 1,
            }
        return {
            "status": "blocked",
            "admission_action": "block",
            "active_count": 1,
            "queued_count": 0,
            "queue_depth": 0,
            "max_concurrent": 1,
        }

    async def fake_submit(**kwargs):
        raise AssertionError("second capacity block should happen before Pixelle")

    monkeypatch.setattr("app.services.image_creation_service.preview_image_capacity", fake_capacity, raising=False)
    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "race for capacity",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_CAPACITY_BLOCKED"
    assert calls == [model.id, model.id]
    assert db.query(ImageCreationTask).filter(ImageCreationTask.prompt == "race for capacity").count() == 0


@pytest.mark.parametrize("message", [
    "Bearer sk-live-abc123 pixelle unavailable",
    "{'authorization': 'Bearer sk-live-json'} pixelle unavailable",
    "Authorization=Bearer sk-live-eq pixelle unavailable",
    "access_token=abc client_secret=def token=ghi api key: jkl pixelle unavailable",
])
def test_redact_provider_error_removes_common_provider_secret_formats(message):
    redacted = _redact_provider_error(message)
    lowered = redacted.lower()

    assert "pixelle unavailable" in redacted
    assert "sk-live" not in redacted
    assert "abc123" not in redacted
    assert "json" not in redacted
    assert "eq" not in redacted
    assert "abc" not in redacted
    assert "def" not in redacted
    assert "ghi" not in redacted
    assert "jkl" not in redacted
    assert "authorization" not in lowered
    assert "access_token" not in lowered
    assert "client_secret" not in lowered
    assert "api key" not in lowered
    assert "token" not in lowered


def test_create_image_task_records_fallback_trace_when_pixelle_submit_fails(db, monkeypatch):
    model = _seed_model(db)
    fallback = _seed_model(db, name_prefix="fallback-model")
    strategy = _strategy(db, model)
    strategy.fallback_model_ids_json = [fallback.id]
    db.commit()

    async def fake_submit(**kwargs):
        assert kwargs["model_config"]["model_id"] == model.id
        raise RuntimeError("Authorization: Bearer ark-123 api_key=secret pixelle unavailable")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    idempotency_key = f"pixelle-fail-{uuid4().hex}"

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "pixelle unavailable",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "idempotency_key": idempotency_key,
        "cost_confirmation": True,
    })

    task = db.query(ImageCreationTask).filter(ImageCreationTask.idempotency_key == idempotency_key).first()
    trace = task.fallback_trace_json
    trace_text = str(trace)

    assert resp.status_code == 502
    assert task.status == "failed"
    assert task.capacity_lease_id is None
    assert trace["error_code"] == "PIXELLE_IMAGE_SUBMIT_FAILED"
    assert trace["fallback_candidates"][0]["model_id"] == fallback.id
    assert trace["rescue_actions"][0]["type"] == "retry_with_fallback_model"
    assert "ark-123" not in trace_text
    assert "Authorization" not in trace_text
    assert "api_key" not in trace_text


def test_sync_image_task_redacts_failed_status_and_records_fallback_trace(db, monkeypatch):
    model = _seed_model(db)
    fallback = _seed_model(db, name_prefix="sync-fallback-model")
    strategy = _strategy(db, model)
    strategy.fallback_model_ids_json = [fallback.id]
    db.commit()

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "sync-failed-stage"}

    async def fake_get_stage_task(db_arg, task_id):
        assert task_id == "sync-failed-stage"
        return {
            "status": "failed",
            "error": "Authorization: Bearer ark-sync-123 api_key=secret sync failed",
            "progress": {"percentage": 25},
            "api_key": "secret-plain",
            "token": "plain-token-value",
            "nested": {"client_secret": "nested-secret-value"},
        }

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    monkeypatch.setattr("app.services.image_creation_service.get_stage_task", fake_get_stage_task)

    create_resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "sync failure",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })
    task_id = create_resp.json()["task"]["id"]

    sync_resp = client.post(f"/api/image-creation/tasks/{task_id}/sync")
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).first()
    persisted_text = str({
        "error_message": task.error_message,
        "provider_response": task.provider_response_json,
        "fallback_trace": task.fallback_trace_json,
    })

    assert sync_resp.status_code == 200
    assert task.status == "failed"
    assert task.error_code == "PIXELLE_IMAGE_SYNC_FAILED"
    assert task.fallback_trace_json["fallback_candidates"][0]["model_id"] == fallback.id
    assert "sync failed" in persisted_text
    assert "ark-sync-123" not in persisted_text
    assert "Authorization" not in persisted_text
    assert "api_key" not in persisted_text
    assert "secret-plain" not in persisted_text
    assert "plain-token-value" not in persisted_text
    assert "nested-secret-value" not in persisted_text


def test_task_payload_includes_production_timeline(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "timeline-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "timeline",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    timeline = resp.json()["task"]["timeline"]
    assert [item["key"] for item in timeline] == ["preview", "snapshot", "queue", "generation", "review", "approval"]
    assert timeline[1]["status"] == "completed"
    assert timeline[3]["status"] in {"queued", "running"}


def test_create_image_task_rejects_stale_strategy_version(db):
    model = _seed_model(db)
    strategy = _strategy(db, model)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "stale",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version - 1,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_STRATEGY_VERSION_CONFLICT"


def test_create_image_task_rejects_stale_selection_preview_hash(db):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "prompt": "preview default model",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "preview drift",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": "stale-hash",
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_SELECTION_PREVIEW_DRIFT"


def test_create_image_task_rejects_selection_preview_when_request_changes(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "prompt": "preview default model",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "output_format": "png",
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for drifted preview")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "preview drift",
        "count": 1,
        "output_format": "jpeg",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_SELECTION_PREVIEW_DRIFT"


def test_create_image_task_accepts_preview_with_strategy_default_model(db, monkeypatch):
    model = _seed_model(db)
    fallback = _seed_model(db, name_prefix="preview-fallback-model")
    strategy = _strategy(db, model)
    strategy.fallback_model_ids_json = [fallback.id]
    db.commit()
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "prompt": "preview default model",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "preview-default-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "preview default model",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    assert resp.json()["task"]["model_id"] == model.id
    explanation = resp.json()["task"]["selection_explanation"]
    assert explanation["candidate_count"] >= 2
    assert explanation["fallback_candidates"][0]["model_id"] == fallback.id
    assert explanation["resolved_capability_key"] == "text_to_image"


def test_create_image_task_accepts_preview_with_strategy_default_destination_role(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "prompt": "preview default destination",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "preview-default-destination-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "preview default destination",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    assert resp.json()["task"]["destination_role"] == strategy.destination_role


def test_image_creation_routes_reject_non_admin_role(db):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="auth",
        status="completed",
        count=1,
        target_count=1,
        completed_count=1,
    )
    db.add(task)
    db.commit()
    asset = ImageCreationAsset(
        task_id=task.id,
        asset_type="image",
        asset_kind="image",
        url="http://example.test/auth.png",
        status="approved",
        version=1,
    )
    db.add(asset)
    db.commit()

    app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "operator")
    try:
        responses = [
            client.post("/api/image-creation/tasks", json={
                "mode": "text_to_image",
                "prompt": "auth",
                "count": 1,
                "strategy_id": strategy.id,
                "strategy_version": strategy.version,
                "cost_confirmation": True,
            }),
            client.get(f"/api/image-creation/tasks/{task.id}"),
            client.post(f"/api/image-creation/tasks/{task.id}/sync"),
            client.get("/api/image-creation/assets"),
            client.post(f"/api/image-creation/assets/{asset.id}/review", json={
                "action": "approve",
                "asset_version": asset.version,
            }),
            client.post(f"/api/image-creation/assets/{asset.id}/edit", json={
                "prompt": "edit",
                "count": 1,
                "cost_confirmation": True,
            }),
        ]
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")

    assert [resp.status_code for resp in responses] == [403, 403, 403, 403, 403, 403]


def test_create_image_task_accepts_preview_with_same_source_and_reference(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    source_url = "http://example.test/source.png"
    reference_images = [{"url": "http://example.test/ref.png", "role": "style"}]
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "prompt": "source reference same",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "source_url": source_url,
        "reference_images": reference_images,
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "preview-source-reference-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "source reference same",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "source_url": source_url,
        "reference_images": reference_images,
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 200


def test_http_selection_preview_keeps_source_and_reference_fields_for_create(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    preview_resp = client.post("/api/image-production/selection-preview", json={
        "mode": "text_to_image",
        "prompt": "http preview",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "source_url": "http://example.test/source.png",
        "reference_images": [{"url": "http://example.test/ref.png", "role": "style"}],
        "provider_options": {"watermark": True},
    })
    preview = preview_resp.json()

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "http-preview-source-reference-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "http preview",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "source_url": "http://example.test/source.png",
        "reference_images": [{"url": "http://example.test/ref.png", "role": "style"}],
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert preview_resp.status_code == 200
    assert resp.status_code == 200


def test_create_image_task_accepts_preview_with_asset_source_and_reference(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    source_task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="asset source",
        status="completed",
        count=1,
        target_count=1,
        completed_count=1,
    )
    db.add(source_task)
    db.commit()
    source_asset = ImageCreationAsset(
        task_id=source_task.id,
        asset_type="image",
        asset_kind="image",
        url="http://example.test/source-asset.png",
        status="approved",
        version=1,
        slot_key="source",
    )
    reference_asset = ImageCreationAsset(
        task_id=source_task.id,
        asset_type="image",
        asset_kind="image",
        url="http://example.test/reference-asset.png",
        status="approved",
        version=1,
        slot_key="reference",
    )
    db.add_all([source_asset, reference_asset])
    db.commit()
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "prompt": "asset preview",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "source_asset_id": source_asset.id,
        "reference_images": [{"asset_id": reference_asset.id, "role": "style"}],
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "preview-asset-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "asset preview",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "source_asset_id": source_asset.id,
        "reference_images": [{"asset_id": reference_asset.id, "role": "style"}],
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 200


def test_create_image_task_rejects_preview_when_reference_changes(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "reference_images": [{"url": "http://example.test/ref-a.png"}],
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for reference drift")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "reference changed",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "reference_images": [{"url": "http://example.test/ref-b.png"}],
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_SELECTION_PREVIEW_DRIFT"


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id", [None, "other-user-id"])
async def test_create_image_task_rejects_selection_preview_user_scope(db, monkeypatch, user_id):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for forbidden preview")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    payload = {
        "mode": "text_to_image",
        "prompt": "preview scope",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    }
    if user_id is not None:
        payload["user_id"] = user_id

    with pytest.raises(HTTPException) as exc_info:
        await create_image_task(db, payload)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_code"] == "IMAGE_SELECTION_PREVIEW_FORBIDDEN"


def test_create_image_task_rejects_old_preview_after_strategy_version_changes(db):
    model = _seed_model(db)
    strategy = _strategy(db, model)
    preview = create_selection_preview(db, {
        "mode": "text_to_image",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "provider_options": {"watermark": True},
    }, user_id="test-user-id")
    strategy.version += 1
    db.commit()

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "old preview",
        "count": 1,
        "strategy_id": strategy.id,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "selection_preview_id": preview["selection_preview_id"],
        "selection_preview_request_hash": preview["request_hash"],
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_SELECTION_PREVIEW_DRIFT"
