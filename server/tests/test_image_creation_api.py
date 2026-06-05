import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db_models import AIModel, ImageCreationAsset, ImageCreationReviewRecord, ImageCreationTask
from app.main import app
from app.routers.image_creation import CreateImageTaskRequest
from app.services.crypto import encrypt
from app.services.image_creation_service import normalized_request_hash


client = TestClient(app)


def _seed_image_model(db, scene_key="image_generation", capabilities=None, limits=None, provider_options_schema=None):
    config_json = {
        "scene_key": scene_key,
        "capabilities": capabilities or {"text_to_image": True},
        "limits": limits or {"max_output_images": 15, "max_reference_images": 14},
    }
    if provider_options_schema is not None:
        config_json["provider_options_schema"] = provider_options_schema
    model = AIModel(
        name=f"{scene_key}-test-{uuid4().hex}",
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret"),
        model_name=f"mock-image-{uuid4().hex}",
        enabled=True,
        config_json=config_json,
    )
    db.add(model)
    db.commit()
    return model


def _error_code(resp):
    body = resp.json()
    if "error_code" in body:
        return body["error_code"]
    return body["detail"]["error_code"]


def test_upload_image_saves_to_static_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.image_creation_storage.IMAGE_CREATION_ROOT", tmp_path / "image-creation")

    resp = client.post(
        "/api/image-creation/uploads",
        files={"file": ("source.png", b"image-bytes", "image/png")},
    )

    assert resp.status_code == 200
    data = resp.json()
    checksum = hashlib.sha256(b"image-bytes").hexdigest()
    assert data["ok"] is True
    assert data["checksum"] == checksum
    assert data["size_bytes"] == len(b"image-bytes")
    assert data["url"].endswith(f"/static/image-creation/uploads/{checksum}.png")


def test_create_text_to_image_task_submits_pixelle(db, monkeypatch):
    _seed_image_model(db)
    calls = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-1"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "rainy night street",
        "count": 1,
        "size": "3K",
        "idempotency_key": "idem-1",
        "destination_role": "image_to_video_input",
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["task"]["pixelle_task_id"] == "stage-1"
    assert data["task"]["provider_task_id"] == "stage-1"
    assert calls[0]["mode"] == "text_to_image"
    assert calls[0]["context"]["destination_role"] == "image_to_video_input"


def test_reusing_idempotency_key_with_different_request_returns_conflict(db, monkeypatch):
    _seed_image_model(db)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "stage-1"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    first = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "rainy night street",
        "count": 1,
        "idempotency_key": "same-key",
        "cost_confirmation": True,
    })
    second = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "sunny street",
        "count": 1,
        "idempotency_key": "same-key",
        "cost_confirmation": True,
    })

    assert first.status_code == 200
    assert second.status_code == 409
    assert _error_code(second) == "IMAGE_TASK_CONFLICT"


def test_image_to_image_requires_source_image_and_does_not_submit(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run when the source image is missing")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "image_to_image",
        "prompt": "make the lighting warmer",
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert _error_code(resp) == "SOURCE_IMAGE_REQUIRED"


def test_create_rejects_private_source_url_before_submit(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for unsafe source URLs")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "image_to_image",
        "prompt": "make the lighting warmer",
        "source_url": "http://127.0.0.1/private.png",
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert _error_code(resp) == "IMAGE_URL_UNSAFE"


def test_create_rejects_source_url_that_resolves_to_private_ip(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})

    def fake_getaddrinfo(host, *args, **kwargs):
        assert host == "private.example"
        return [(None, None, None, None, ("10.0.0.7", 0))]

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for DNS-private source URLs")

    monkeypatch.setattr("app.services.image_creation_service.socket.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "image_to_image",
        "prompt": "make the lighting warmer",
        "source_url": "https://private.example/source.png",
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert _error_code(resp) == "IMAGE_URL_UNSAFE"


def test_create_rejects_provider_options_that_override_core_payload(db, monkeypatch):
    _seed_image_model(
        db,
        provider_options_schema={"watermark": {"type": "boolean"}},
    )

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for protected provider options")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "rainy night street",
        "provider_options": {"model": "unapproved-model"},
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert _error_code(resp) == "IMAGE_PROVIDER_OPTIONS_INVALID"


def test_create_rejects_schema_declared_secret_provider_option(db, monkeypatch):
    _seed_image_model(
        db,
        provider_options_schema={"apiKey": {"type": "string"}},
    )

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for secret provider options")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "rainy night street",
        "provider_options": {"apiKey": "leak"},
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert _error_code(resp) == "IMAGE_PROVIDER_OPTIONS_INVALID"


def test_create_rejects_nested_secret_provider_option(db, monkeypatch):
    _seed_image_model(
        db,
        provider_options_schema={"advanced": {"type": "object"}},
    )

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for nested secret provider options")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "rainy night street",
        "provider_options": {"advanced": {"apiKey": "leak"}},
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert _error_code(resp) == "IMAGE_PROVIDER_OPTIONS_INVALID"


def test_image_to_image_resolves_source_asset_url_for_pixelle(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})
    source_task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="source",
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
        url="http://example.test/source.png",
        status="approved",
        version=1,
        slot_key="source-slot",
    )
    db.add(source_asset)
    db.commit()
    calls = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-source"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "image_to_image",
        "prompt": "make the lighting warmer",
        "source_asset_id": source_asset.id,
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    assert calls[0]["source_image_url"] == source_asset.url
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == resp.json()["task"]["id"]).one()
    assert task.source_asset_id == source_asset.id
    assert task.source_url == source_asset.url


def test_image_to_image_missing_source_asset_returns_404(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run when source asset is missing")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "image_to_image",
        "prompt": "make the lighting warmer",
        "source": {"asset_id": "missing-asset-id"},
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 404
    assert _error_code(resp) == "SOURCE_ASSET_NOT_FOUND"


def test_image_to_image_source_asset_without_public_url_returns_400(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})
    source_task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="source",
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
        local_path="C:\\tmp\\source.png",
        storage_path="outputs/source.png",
        status="approved",
        version=1,
        slot_key="source-slot",
    )
    db.add(source_asset)
    db.commit()

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run when source asset has no public URL")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "image_to_image",
        "prompt": "make the lighting warmer",
        "source": {"asset_id": source_asset.id},
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert _error_code(resp) == "SOURCE_ASSET_URL_REQUIRED"


def test_existing_reserved_idempotency_task_returns_without_submit(db, monkeypatch):
    payload = {
        "mode": "text_to_image",
        "prompt": "already reserved",
        "count": 1,
        "idempotency_key": "reserved-key",
        "cost_confirmation": True,
    }
    existing = ImageCreationTask(
        user_id="test-user-id",
        idempotency_key="reserved-key",
        request_hash=normalized_request_hash(CreateImageTaskRequest(**payload).model_dump()),
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="already reserved",
        status="queued",
        count=1,
        target_count=1,
    )
    db.add(existing)
    db.commit()

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run for an existing reserved task")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json=payload)

    assert resp.status_code == 200
    assert resp.json()["task"]["id"] == existing.id
    assert resp.json()["task"]["status"] == "queued"


def test_multi_reference_requires_two_references_and_does_not_submit(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"multi_reference_to_image": True})

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run when references are insufficient")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "multi_reference_to_image",
        "prompt": "merge style and character",
        "reference_images": [{"url": "http://example.test/a.png"}],
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert _error_code(resp) == "REFERENCE_IMAGES_REQUIRED"


def test_multi_reference_resolves_reference_asset_ids(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"multi_reference_to_image": True})
    source_task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="reference",
        status="completed",
        count=1,
        target_count=1,
        completed_count=1,
    )
    db.add(source_task)
    db.commit()
    reference_asset = ImageCreationAsset(
        task_id=source_task.id,
        asset_type="image",
        asset_kind="image",
        url="http://example.test/reference.png",
        status="approved",
        version=1,
        slot_key="reference-slot",
    )
    db.add(reference_asset)
    db.commit()
    calls = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-reference"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "multi_reference_to_image",
        "prompt": "merge style and character",
        "reference_images": [
            {"asset_id": reference_asset.id},
            {"url": "http://example.test/second.png"},
        ],
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    assert calls[0]["reference_images"] == [
        {"asset_id": reference_asset.id, "url": reference_asset.url, "type": "asset"},
        {"url": "http://example.test/second.png"},
    ]


def test_list_assets_filters_approved_destination(db):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="asset seed",
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
        url="http://example.test/approved.png",
        status="approved",
        version=1,
        destination_role="image_to_video_input",
        prompt_hash="hash",
        is_latest=True,
        audit_status="approved",
        manual_review_status="approved",
        storage_status="persisted",
    )
    db.add(asset)
    db.commit()

    resp = client.get("/api/image-creation/assets?status=approved&destination_role=image_to_video_input")

    assert resp.status_code == 200
    assert resp.json()["assets"][0]["id"] == asset.id
    assert resp.json()["total"] == 1


def test_sync_persists_completed_assets_without_duplicates(db, monkeypatch):
    _seed_image_model(db)
    copied = []

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "stage-sync"}

    async def fake_status(db, stage_task_id):
        return {
            "ok": True,
            "status": "succeeded",
            "assets": [{
                "url": "http://example.test/output.png",
                "local_path": "outputs/output.png",
                "metadata": {"group_id": "group-1", "group_index": 0},
                "provider_task_id": "provider-asset-1",
            }],
        }

    async def fake_copy_external(url):
        copied.append(url)
        return {
            "url": "http://127.0.0.1:8000/static/image-creation/outputs/copied.png",
            "local_path": "D:\\outputs\\copied.png",
            "storage_path": "outputs/copied.png",
            "checksum": "checksum",
            "size_bytes": 12,
            "mime_type": "image/png",
        }

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    monkeypatch.setattr("app.services.image_creation_service.get_stage_task", fake_status)
    monkeypatch.setattr("app.services.image_creation_service._copy_external_image", fake_copy_external)

    created = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "sync asset",
        "count": 1,
        "destination_role": "image_to_video_input",
        "idempotency_key": "sync-1",
        "cost_confirmation": True,
    })
    task_id = created.json()["task"]["id"]

    first = client.post(f"/api/image-creation/tasks/{task_id}/sync")
    second = client.post(f"/api/image-creation/tasks/{task_id}/sync")

    assert first.status_code == 200
    assert second.status_code == 200
    assets = db.query(ImageCreationAsset).filter(ImageCreationAsset.task_id == task_id).all()
    assert len(assets) == 1
    assert assets[0].status == "review_pending"
    assert assets[0].url.endswith("/static/image-creation/outputs/copied.png")
    assert assets[0].storage_path == "outputs/copied.png"
    assert copied == ["http://example.test/output.png"]


def test_sync_running_task_accepts_pixelle_progress_object(db, monkeypatch):
    _seed_image_model(db)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "stage-running"}

    async def fake_status(db, stage_task_id):
        return {
            "ok": True,
            "status": "running",
            "progress": {"current": 2, "total": 5, "message": "Generating"},
        }

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    monkeypatch.setattr("app.services.image_creation_service.get_stage_task", fake_status)

    created = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "running asset",
        "count": 1,
        "idempotency_key": "running-progress-1",
        "cost_confirmation": True,
    })
    task_id = created.json()["task"]["id"]

    resp = client.post(f"/api/image-creation/tasks/{task_id}/sync")

    assert resp.status_code == 200
    task = db.query(ImageCreationTask).filter_by(id=task_id).one()
    assert task.status == "running"
    assert task.progress == 0.4


def test_sync_normalizes_pixelle_file_url_for_preview_and_reuse(db, monkeypatch):
    _seed_image_model(db)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "stage-file-url"}

    async def fake_status(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "url": "/api/files/output/stage-file-url/image.png",
                "local_path": "output/stage-file-url/image.png",
                "metadata": {"group_id": "group-file", "group_index": 0},
            }],
        }

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    monkeypatch.setattr("app.services.image_creation_service.get_stage_task", fake_status)

    created = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "file url asset",
        "count": 1,
        "idempotency_key": "file-url-1",
        "cost_confirmation": True,
    })
    task_id = created.json()["task"]["id"]

    resp = client.post(f"/api/image-creation/tasks/{task_id}/sync")

    assert resp.status_code == 200
    asset = db.query(ImageCreationAsset).filter_by(task_id=task_id).one()
    assert asset.url.startswith("http://127.0.0.1:8000/api/image-creation/pixelle-files/")
    assert "output%2Fstage-file-url%2Fimage.png" in asset.url
    assert asset.local_path == "output/stage-file-url/image.png"


def test_pixelle_file_proxy_rejects_non_output_paths():
    resp = client.get("/api/image-creation/pixelle-files/templates/1080x1920/image.html")

    assert resp.status_code == 403
    assert _error_code(resp) == "PIXELLE_FILE_PATH_FORBIDDEN"


def test_review_asset_replaces_latest_review(db):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="review asset",
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
        url="http://example.test/review.png",
        status="review_pending",
        version=1,
        slot_key="review-slot",
    )
    db.add(asset)
    db.commit()
    old_review = ImageCreationReviewRecord(
        task_id=task.id,
        asset_id=asset.id,
        review_type="human",
        reviewer_type="human",
        status="review_pending",
        action="approve",
        asset_version=1,
        is_latest_asset_review=True,
    )
    db.add(old_review)
    db.commit()

    reject = client.post(f"/api/image-creation/assets/{asset.id}/review", json={"action": "reject", "asset_version": 1})

    assert reject.status_code == 200
    db.refresh(asset)
    assert asset.status == "rejected"
    latest_count = sum(1 for review in reject.json()["reviews"] if review["is_latest_asset_review"])
    assert latest_count == 1
    db.refresh(old_review)
    assert old_review.is_latest_asset_review is False


def test_review_asset_reject_disallowed_after_approval(db):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="approved asset",
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
        url="http://example.test/approved.png",
        status="approved",
        audit_status="approved",
        manual_review_status="approved",
        version=1,
        slot_key="approved-slot",
    )
    db.add(asset)
    db.commit()

    resp = client.post(f"/api/image-creation/assets/{asset.id}/review", json={"action": "reject", "asset_version": 1})

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "IMAGE_REVIEW_ACTION_NOT_ALLOWED"
    assert detail["affected_ids"] == [asset.id]
    assert detail["retryable"] is False


def test_review_asset_requires_asset_version(db):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="review asset",
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
        url="http://example.test/review.png",
        status="review_pending",
        version=1,
        slot_key="review-slot-required",
    )
    db.add(asset)
    db.commit()

    resp = client.post(f"/api/image-creation/assets/{asset.id}/review", json={"action": "approve"})

    assert resp.status_code == 422


def test_repaint_asset_creates_image_to_image_task_from_source_asset(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})
    source_task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="source",
        status="completed",
        series_id="series-1",
        episode_id="episode-1",
        count=1,
        target_count=1,
        completed_count=1,
    )
    db.add(source_task)
    db.commit()
    source_asset = ImageCreationAsset(
        task_id=source_task.id,
        series_id="series-1",
        episode_id="episode-1",
        asset_type="image",
        asset_kind="image",
        url="http://example.test/source-edit.png",
        status="rejected",
        version=1,
        slot_key="source-edit-slot",
    )
    db.add(source_asset)
    db.commit()
    calls = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-edit"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post(f"/api/image-creation/assets/{source_asset.id}/edit", json={
        "prompt": "make the lighting cinematic",
        "count": 1,
        "action": "repaint",
        "asset_version": source_asset.version,
        "idempotency_key": "edit-source-1",
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["task"]["mode"] == "image_to_image"
    assert data["task"]["series_id"] == "series-1"
    assert data["task"]["episode_id"] == "episode-1"
    assert calls[0]["source_image_url"] == source_asset.url
    db.refresh(source_asset)
    assert source_asset.status == "regenerating"


def test_copy_asset_creates_image_to_image_task_without_mutating_source_asset(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})
    source_task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="source",
        status="completed",
        series_id="series-1",
        episode_id="episode-1",
        count=1,
        target_count=1,
        completed_count=1,
    )
    db.add(source_task)
    db.commit()
    source_asset = ImageCreationAsset(
        task_id=source_task.id,
        series_id="series-1",
        episode_id="episode-1",
        asset_type="image",
        asset_kind="image",
        url="http://example.test/source-copy.png",
        status="approved",
        version=1,
        slot_key="source-copy-slot",
    )
    db.add(source_asset)
    db.commit()
    calls = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-copy"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post(f"/api/image-creation/assets/{source_asset.id}/edit", json={
        "prompt": "copy as a fresh task",
        "count": 1,
        "action": "copy_as_new_task",
        "asset_version": source_asset.version,
        "idempotency_key": "copy-source-1",
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["task"]["mode"] == "image_to_image"
    assert calls[0]["source_image_url"] == source_asset.url
    db.refresh(source_asset)
    assert source_asset.status == "approved"


def test_repaint_asset_rejects_action_not_allowed_for_approved_asset(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})
    source_task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="source",
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
        url="http://example.test/source-approved.png",
        status="approved",
        version=1,
        slot_key="source-approved-slot",
    )
    db.add(source_asset)
    db.commit()
    calls = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-should-not-run"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post(f"/api/image-creation/assets/{source_asset.id}/edit", json={
        "prompt": "should not repaint approved",
        "count": 1,
        "action": "repaint",
        "asset_version": source_asset.version,
        "idempotency_key": "repaint-approved-blocked",
        "cost_confirmation": True,
    })

    assert resp.status_code == 409
    assert _error_code(resp) == "IMAGE_ASSET_ACTION_NOT_ALLOWED"
    assert calls == []
    db.refresh(source_asset)
    assert source_asset.status == "approved"


def test_edit_asset_validates_source_before_idempotency_return(db, monkeypatch):
    _seed_image_model(db, scene_key="image_editing", capabilities={"image_to_image": True})
    source_task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="source",
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
        url="http://example.test/source-for-idempotency.png",
        status="approved",
        version=1,
        slot_key="source-idempotency-slot",
    )
    db.add(source_asset)
    db.commit()
    calls = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-edit-idempotent"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    body = {
        "prompt": "make the lighting cinematic",
        "count": 1,
        "action": "copy_as_new_task",
        "asset_version": source_asset.version,
        "idempotency_key": "edit-source-idempotent",
        "cost_confirmation": True,
    }

    first = client.post(f"/api/image-creation/assets/{source_asset.id}/edit", json=body)

    assert first.status_code == 200
    assert len(calls) == 1

    db.refresh(source_asset)
    source_asset.url = ""
    source_asset.local_path = "C:\\tmp\\not-public.png"
    source_asset.storage_path = "outputs/not-public.png"
    source_asset.status = "approved"
    db.commit()

    second = client.post(f"/api/image-creation/assets/{source_asset.id}/edit", json=body)

    assert second.status_code == 400
    assert _error_code(second) == "SOURCE_ASSET_URL_REQUIRED"
    assert len(calls) == 1
    db.refresh(source_asset)
    assert source_asset.status == "approved"
