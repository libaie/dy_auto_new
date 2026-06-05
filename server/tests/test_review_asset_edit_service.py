import pytest

from app.db_models import (
    Episode,
    ImageCreationAsset,
    ImageCreationTask,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
from app.services.review_asset_edit_service import (
    ReviewAssetEditError,
    _generate_edited_image,
    edit_image_asset,
    void_asset_version,
)


def create_run_with_image_asset(db):
    series = Series(title="Series", logline="Story", genre="drama", total_episodes=1, target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "old prompt"}]},
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image",
        url="https://cdn.test/old.png",
        version=1,
        status="review_pending",
        is_latest=True,
        copy_status="persisted",
        checksum="abc",
        storage_path="assets/old.png",
        metadata_json={"storyboard_frame": {"frame_id": "frame-001", "image_prompt": "old prompt"}},
    )
    db.add(asset)
    db.commit()
    return run, asset


def test_review_edit_destination_role_is_registered_for_image_creation():
    from app.services.image_creation_service import DESTINATION_ROLES

    assert "video_production_review_edit" in DESTINATION_ROLES


def test_void_asset_version_marks_asset_voided_and_records_review(db):
    _, asset = create_run_with_image_asset(db)

    result = void_asset_version(db, asset.id, reviewer_user_id="user-1", comment="bad face")

    db.refresh(asset)
    review = db.query(VideoReviewRecord).filter(VideoReviewRecord.asset_id == asset.id).one()
    assert result["ok"] is True
    assert asset.status == "voided"
    assert review.review_type == "human"
    assert review.status == "voided"
    assert review.action == "void"
    assert review.comment == "bad face"
    assert review.asset_snapshot_json["id"] == asset.id
    assert review.asset_version == asset.version
    assert review.is_latest_asset_review is True


@pytest.mark.asyncio
async def test_edit_image_asset_creates_new_version_and_demotes_old(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)

    async def fake_generate(db, asset, instruction):
        return {
            "url": "https://cdn.test/new.png",
            "source_url": asset.url,
            "image_creation_task_id": "task-1",
            "image_creation_asset_id": "image-asset-1",
            "copy_status": "persisted",
            "checksum": "def",
            "storage_path": "assets/new.png",
        }

    monkeypatch.setattr("app.services.review_asset_edit_service._generate_edited_image", fake_generate)

    result = await edit_image_asset(db, asset.id, instruction="make hair consistent", expected_version=1)

    db.refresh(asset)
    new_asset = result["asset"]
    assert asset.is_latest is False
    assert new_asset.version == 2
    assert new_asset.status == "review_pending"
    assert new_asset.run_id == asset.run_id
    assert new_asset.episode_id == asset.episode_id
    assert new_asset.frame_id == asset.frame_id
    assert new_asset.source_version == asset.version
    assert new_asset.metadata_json["source_asset_id"] == asset.id
    assert new_asset.metadata_json["source_version"] == asset.version
    assert new_asset.metadata_json["edit_instruction"] == "make hair consistent"
    assert new_asset.metadata_json["image_creation_task_id"] == "task-1"
    assert new_asset.metadata_json["image_creation_asset_id"] == "image-asset-1"


@pytest.mark.asyncio
async def test_edit_image_asset_reserves_asset_before_provider_call(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)
    observed_status = None

    async def fake_generate(db, asset, instruction):
        nonlocal observed_status
        db.refresh(asset)
        observed_status = asset.status
        return {
            "url": "https://cdn.test/new.png",
            "copy_status": "persisted",
            "checksum": "def",
            "storage_path": "assets/new.png",
        }

    monkeypatch.setattr("app.services.review_asset_edit_service._generate_edited_image", fake_generate)

    await edit_image_asset(db, asset.id, instruction="make hair consistent", expected_version=1)

    assert observed_status == "regenerating"


@pytest.mark.asyncio
async def test_edit_image_asset_surfaces_queued_task_without_demoting_or_creating(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)

    async def fake_generate(db, asset, instruction):
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_QUEUED",
            "Image edit task is queued.",
            {"image_task_id": "task-1", "status": "queued"},
        )

    monkeypatch.setattr("app.services.review_asset_edit_service._generate_edited_image", fake_generate)

    with pytest.raises(ReviewAssetEditError) as exc:
        await edit_image_asset(db, asset.id, instruction="make hair consistent")

    assert exc.value.code == "IMAGE_EDIT_TASK_QUEUED"
    db.refresh(asset)
    assert asset.is_latest is True
    assert db.query(VideoProductionAsset).count() == 1


@pytest.mark.asyncio
async def test_edit_image_asset_surfaces_pending_task_without_demoting_or_creating(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)

    async def fake_generate(db, asset, instruction):
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_PENDING",
            "Image edit task has not produced a usable URL yet.",
            {"image_task_id": "task-1", "status": "running"},
        )

    monkeypatch.setattr("app.services.review_asset_edit_service._generate_edited_image", fake_generate)

    with pytest.raises(ReviewAssetEditError) as exc:
        await edit_image_asset(db, asset.id, instruction="make hair consistent")

    assert exc.value.code == "IMAGE_EDIT_TASK_PENDING"
    db.refresh(asset)
    assert asset.is_latest is True
    assert db.query(VideoProductionAsset).count() == 1


@pytest.mark.asyncio
async def test_generate_edited_image_uses_existing_image_creation_path_payload(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)
    captured_payload = {}

    async def fake_create_image_task(db, payload):
        captured_payload.update(payload)
        task = ImageCreationTask(
            mode="image_to_image",
            output_mode="single",
            capability_key="image_to_image",
            status="running",
            prompt=payload["prompt"],
            pixelle_task_id="provider-task-1",
            provider_task_id="provider-task-1",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    async def fake_sync_image_task(db, task_id):
        task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).one()
        db.add(ImageCreationAsset(
            task_id=task.id,
            url="https://cdn.test/edited.png",
            status="review_pending",
            slot_key="default",
            storage_status="persisted",
            checksum="sha256-edited",
            storage_path="assets/edited.png",
            source_url=asset.url,
        ))
        task.status = "completed"
        db.commit()
        db.refresh(task)
        return task

    monkeypatch.setattr("app.services.image_creation_service.create_image_task", fake_create_image_task)
    monkeypatch.setattr("app.services.image_creation_service.sync_image_task", fake_sync_image_task)

    result = await _generate_edited_image(db, asset, "fix face")

    assert captured_payload["mode"] == "image_to_image"
    assert captured_payload["source"] == {"type": "url", "url": asset.url}
    assert "source_asset_id" not in captured_payload
    assert captured_payload["destination_role"] == "video_production_review_edit"
    assert captured_payload["destination_context"]["video_asset_id"] == asset.id
    assert captured_payload["cost_confirmation"] is True
    assert result["url"] == "https://cdn.test/edited.png"
    assert result["image_creation_task_id"]
    assert result["image_creation_asset_id"]


@pytest.mark.asyncio
async def test_generate_edited_image_uses_bounded_idempotency_key_for_long_instruction(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)
    captured_payload = {}
    long_instruction = "x" * 2000

    async def fake_create_image_task(db, payload):
        captured_payload.update(payload)
        task = ImageCreationTask(
            mode="image_to_image",
            output_mode="single",
            capability_key="image_to_image",
            status="queued",
            prompt=payload["prompt"],
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    monkeypatch.setattr("app.services.image_creation_service.create_image_task", fake_create_image_task)

    with pytest.raises(ReviewAssetEditError) as exc:
        await _generate_edited_image(db, asset, long_instruction)

    assert exc.value.code == "IMAGE_EDIT_TASK_QUEUED"
    assert captured_payload["prompt"] == long_instruction
    assert len(captured_payload["idempotency_key"]) <= 160
    assert long_instruction not in captured_payload["idempotency_key"]
    assert captured_payload["idempotency_key"].startswith(f"video-review-edit:{asset.id}:{asset.version}:")


@pytest.mark.asyncio
async def test_generate_edited_image_maps_returned_failed_task_to_provider_failure(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)

    async def fake_create_image_task(db, payload):
        task = ImageCreationTask(
            mode="image_to_image",
            output_mode="single",
            capability_key="image_to_image",
            status="failed",
            prompt=payload["prompt"],
            error_code="PIXELLE_IMAGE_SUBMIT_FAILED",
            error_message="Provider rejected prompt",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    monkeypatch.setattr("app.services.image_creation_service.create_image_task", fake_create_image_task)

    with pytest.raises(ReviewAssetEditError) as exc:
        await _generate_edited_image(db, asset, "fix face")

    assert exc.value.code == "IMAGE_EDIT_PROVIDER_FAILED"
    assert exc.value.details["image_task_id"]
    assert exc.value.details["status"] == "failed"
    assert exc.value.details["error_code"] == "PIXELLE_IMAGE_SUBMIT_FAILED"
    assert exc.value.details["error_message"] == "Provider rejected prompt"


def test_void_stale_asset_version_raises(db):
    _, asset = create_run_with_image_asset(db)
    asset.is_latest = False
    db.commit()

    with pytest.raises(ReviewAssetEditError) as exc:
        void_asset_version(db, asset.id, reviewer_user_id="user-1", comment="old")

    assert exc.value.code == "STALE_ASSET_VERSION"


@pytest.mark.asyncio
async def test_edit_stale_asset_version_raises_before_provider_call(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)
    called = False

    async def fake_generate(db, asset, instruction):
        nonlocal called
        called = True
        return {"url": "https://cdn.test/new.png"}

    monkeypatch.setattr("app.services.review_asset_edit_service._generate_edited_image", fake_generate)

    with pytest.raises(ReviewAssetEditError) as exc:
        await edit_image_asset(db, asset.id, instruction="make hair consistent", expected_version=2)

    assert exc.value.code == "STALE_ASSET_VERSION"
    assert called is False


@pytest.mark.asyncio
async def test_edit_reserved_asset_version_raises_before_provider_call(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)
    asset.status = "regenerating"
    db.commit()
    called = False

    async def fake_generate(db, asset, instruction):
        nonlocal called
        called = True
        return {"url": "https://cdn.test/new.png"}

    monkeypatch.setattr("app.services.review_asset_edit_service._generate_edited_image", fake_generate)

    with pytest.raises(ReviewAssetEditError) as exc:
        await edit_image_asset(db, asset.id, instruction="make hair consistent", expected_version=1)

    assert exc.value.code == "IMAGE_EDIT_IN_PROGRESS"
    assert called is False
