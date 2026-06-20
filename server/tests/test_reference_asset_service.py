import pytest
from app.db.models import Character, CharacterAnchor, ImageCreationAsset, ImageCreationTask, Scene, SceneAnchor, Series


@pytest.mark.asyncio
async def test_invalid_character_slot_raises_reference_slot_invalid(db):
    from app.domains.creative_library.reference_asset_service import (
        ReferenceAssetError,
        generate_character_reference_images,
    )

    character = Character(name="Lin")
    db.add(character)
    db.commit()

    with pytest.raises(ReferenceAssetError) as exc_info:
        await generate_character_reference_images(db, character.id, slot="portrait")

    assert exc_info.value.code == "REFERENCE_SLOT_INVALID"


@pytest.mark.asyncio
async def test_character_single_slot_generation_updates_only_requested_url_and_meta(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    character = Character(
        name="Lin",
        role_type="protagonist",
        gender="female",
        age_range="28-32",
        personality="calm and precise",
        appearance_desc="short black hair and sharp eyes",
        outfit_desc="long gray coat",
    )
    db.add(character)
    db.commit()

    prompts = []

    async def fake_generate_reference_url(db_session, prompt, scene_key="image_generation", **kwargs):
        prompts.append(prompt)
        return "https://cdn.test/lin-side.png"

    monkeypatch.setattr(reference_asset_service, "generate_reference_url", fake_generate_reference_url)

    result = await reference_asset_service.generate_character_reference_images(
        db, character.id, slot="avatar_side_url"
    )

    assert result["ok"] is True
    assert result["generated"] == [{"slot": "avatar_side_url", "url": "https://cdn.test/lin-side.png"}]
    assert result["missing_assets"] == []
    assert "side-profile character anchor sheet" in prompts[0]

    db.expire_all()
    saved = db.query(Character).filter(Character.id == character.id).one()
    anchor = db.query(CharacterAnchor).filter_by(character_id=character.id, reference_slot="avatar_side_url").one()
    assert saved.avatar_side_url == "https://cdn.test/lin-side.png"
    assert saved.avatar_front_url is None
    assert saved.avatar_threequarter_url is None
    assert saved.avatar_fullbody_url is None
    assert saved.meta_json["reference_generation"]["avatar_side_url"]["url"] == "https://cdn.test/lin-side.png"
    assert saved.meta_json["reference_generation"]["avatar_side_url"]["prompt"] == prompts[0]
    assert saved.meta_json["reference_generation"]["avatar_side_url"]["generated_at"]
    assert anchor.name == "Lin"
    assert anchor.anchor_image_url == "https://cdn.test/lin-side.png"
    assert anchor.ref_mode == "controlnet_face"
    assert anchor.status == "locked"


@pytest.mark.asyncio
async def test_scene_all_slots_generation_updates_all_reference_urls(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    scene = Scene(
        name="Rain Clinic",
        scene_type="indoor",
        location_desc="small clinic with neon reflections and rain on glass",
        lighting="night",
        mood="mysterious",
    )
    db.add(scene)
    db.commit()

    prompts = []

    async def fake_generate_reference_url(db_session, prompt, scene_key="image_generation", **kwargs):
        prompts.append(prompt)
        return f"https://cdn.test/scene-{len(prompts)}.png"

    monkeypatch.setattr(reference_asset_service, "generate_reference_url", fake_generate_reference_url)

    result = await reference_asset_service.generate_scene_reference_images(db, scene.id)

    assert result["ok"] is True
    assert [item["slot"] for item in result["generated"]] == [
        "reference_wideshot_url",
        "reference_midshot_url",
        "reference_aerial_url",
    ]
    assert result["missing_assets"] == []
    assert len(prompts) == 3
    for prompt in prompts:
        lowered = prompt.lower()
        assert "empty environment plate" in lowered
        assert "no people" in lowered
        assert "no humans" in lowered
        assert "no characters" in lowered

    db.expire_all()
    saved = db.query(Scene).filter(Scene.id == scene.id).one()
    anchors = db.query(SceneAnchor).filter_by(scene_id=scene.id).all()
    assert saved.reference_wideshot_url
    assert saved.reference_midshot_url
    assert saved.reference_aerial_url
    assert set(saved.meta_json["reference_generation"]) == {
        "reference_wideshot_url",
        "reference_midshot_url",
        "reference_aerial_url",
    }
    assert {anchor.reference_slot for anchor in anchors} == {
        "reference_wideshot_url",
        "reference_midshot_url",
        "reference_aerial_url",
    }
    assert {anchor.ref_mode for anchor in anchors} == {"image_to_image"}


@pytest.mark.asyncio
async def test_reality_series_context_forces_character_and_scene_reference_prompts_to_live_action(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    series = Series(
        title="控糖日记",
        logline="一位现实生活的普通中老年人老刘用现实真实生活方式管理血糖，每集解决一个日常控糖问题。",
        genre="health",
    )
    character = Character(
        name="老刘",
        role_type="protagonist",
        age_range="55-65",
        appearance_desc="普通中老年男性，生活化，不夸张",
        outfit_desc="浅色 polo 衫和深色长裤",
    )
    scene = Scene(
        name="家庭餐桌",
        scene_type="indoor",
        location_desc="普通居民家中的餐桌",
        lighting="自然 daylight",
        mood="生活化",
    )
    db.add_all([series, character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    db.commit()

    prompts = []

    async def fake_generate_reference_url(db_session, prompt, scene_key="image_generation", **kwargs):
        prompts.append(prompt)
        return f"https://cdn.test/ref-{len(prompts)}.png"

    monkeypatch.setattr(reference_asset_service, "generate_reference_url", fake_generate_reference_url)

    await reference_asset_service.generate_character_reference_images(db, character.id, slot="avatar_front_url")
    await reference_asset_service.generate_scene_reference_images(db, scene.id, slot="reference_wideshot_url")

    assert len(prompts) == 2
    for prompt in prompts:
        assert "photorealistic live-action" in prompt
        assert "real human" in prompt
        assert "documentary realism" in prompt
        assert "no anime" in prompt
        assert "no cartoon" in prompt
        assert "no illustration" in prompt


def test_reference_url_is_usable_rejects_expired_tos_signed_url():
    from datetime import datetime, timezone
    from app.domains.creative_library.reference_asset_service import reference_url_is_usable

    expired = (
        "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/ref.jpeg"
        "?X-Tos-Date=20260528T061838Z&X-Tos-Expires=86400"
    )
    fresh = (
        "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/ref.jpeg"
        "?X-Tos-Date=20260528T061838Z&X-Tos-Expires=86400"
    )

    assert reference_url_is_usable(expired, now=datetime(2026, 6, 2, tzinfo=timezone.utc)) is False
    assert reference_url_is_usable(fresh, now=datetime(2026, 5, 28, 7, 0, tzinfo=timezone.utc)) is True
    assert reference_url_is_usable("https://cdn.test/stable-reference.png") is True


@pytest.mark.asyncio
async def test_character_all_slots_regenerates_expired_signed_reference_url(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    expired = (
        "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/ref.jpeg"
        "?X-Tos-Date=20000101T000000Z&X-Tos-Expires=86400"
    )
    character = Character(
        name="Lin",
        avatar_front_url=expired,
        avatar_side_url="https://cdn.test/side.png",
    )
    db.add(character)
    db.commit()

    prompts = []

    async def fake_generate_reference_url(db_session, prompt, scene_key="image_generation", **kwargs):
        prompts.append(prompt)
        return f"https://cdn.test/regenerated-{len(prompts)}.png"

    monkeypatch.setattr(reference_asset_service, "generate_reference_url", fake_generate_reference_url)

    result = await reference_asset_service.generate_character_reference_images(db, character.id, slot="all")

    generated_slots = [item["slot"] for item in result["generated"]]
    assert "avatar_front_url" in generated_slots
    assert "avatar_side_url" not in generated_slots
    db.expire_all()
    saved = db.query(Character).filter(Character.id == character.id).one()
    assert saved.avatar_front_url.startswith("https://cdn.test/regenerated-")
    assert saved.avatar_side_url == "https://cdn.test/side.png"


@pytest.mark.asyncio
async def test_missing_model_capability_maps_to_model_scene_not_configured(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    from fastapi import HTTPException

    async def fake_create_image_task(db_session, payload):
        raise HTTPException(status_code=400, detail={
            "error_code": "IMAGE_CAPABILITY_UNSUPPORTED",
            "message": "missing model",
        })

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)

    with pytest.raises(reference_asset_service.ReferenceAssetError) as exc_info:
        await reference_asset_service.generate_reference_url(db, "prompt")

    assert exc_info.value.code == "MODEL_SCENE_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_generate_reference_url_uses_image_creation_task_pipeline(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    captured_payload = {}

    async def fake_create_image_task(db_session, payload):
        captured_payload.update(payload)
        task = ImageCreationTask(
            mode="text_to_image",
            output_mode="single",
            capability_key="text_to_image",
            status="running",
            prompt=payload["prompt"],
            provider_task_id="provider-task-1",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    async def fake_sync_image_task(db_session, task_id):
        task = db_session.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).one()
        db_session.add(ImageCreationAsset(
            task_id=task.id,
            url="http://127.0.0.1:8000/static/image-creation/outputs/reference.png",
            status="review_pending",
            slot_key="default",
            storage_status="persisted",
        ))
        task.status = "completed"
        db_session.commit()
        db_session.refresh(task)
        return task

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service.sync_image_task", fake_sync_image_task)

    url = await reference_asset_service.generate_reference_url(
        db,
        "reference prompt",
        destination_role="character_anchor_image",
        destination_context={"asset_type": "character", "slot": "avatar_front_url"},
    )

    assert url == "http://127.0.0.1:8000/static/image-creation/outputs/reference.png"
    assert captured_payload["mode"] == "text_to_image"
    assert captured_payload["prompt"] == "reference prompt"
    assert captured_payload["count"] == 1
    assert captured_payload["destination_role"] == "character_anchor_image"
    assert captured_payload["destination_context"] == {"asset_type": "character", "slot": "avatar_front_url"}
    assert captured_payload["cost_confirmation"] is True


@pytest.mark.asyncio
async def test_generate_reference_url_polls_running_provider_task_until_asset_ready(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    async def fake_create_image_task(db_session, payload):
        task = ImageCreationTask(
            mode="text_to_image",
            output_mode="single",
            capability_key="text_to_image",
            status="running",
            prompt=payload["prompt"],
            pixelle_task_id="stage-task-1",
            provider_task_id="stage-task-1",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    calls = {"count": 0}

    async def fake_sync_image_task(db_session, task_id):
        calls["count"] += 1
        task = db_session.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).one()
        if calls["count"] == 1:
            task.status = "running"
            db_session.commit()
            db_session.refresh(task)
            return task
        db_session.add(ImageCreationAsset(
            task_id=task.id,
            url="http://127.0.0.1:8000/static/image-creation/outputs/reference-ready.png",
            status="review_pending",
            slot_key="default",
            storage_status="persisted",
        ))
        task.status = "completed"
        db_session.commit()
        db_session.refresh(task)
        return task

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service.sync_image_task", fake_sync_image_task)
    monkeypatch.setattr(reference_asset_service, "REFERENCE_SYNC_POLL_ATTEMPTS", 3)
    monkeypatch.setattr(reference_asset_service, "REFERENCE_SYNC_POLL_DELAY_SECONDS", 0)

    url = await reference_asset_service.generate_reference_url(db, "reference prompt")

    assert url == "http://127.0.0.1:8000/static/image-creation/outputs/reference-ready.png"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_generate_reference_url_reports_provider_still_running_after_poll_budget(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    async def fake_create_image_task(db_session, payload):
        task = ImageCreationTask(
            mode="text_to_image",
            output_mode="single",
            capability_key="text_to_image",
            status="running",
            prompt=payload["prompt"],
            pixelle_task_id="stage-task-slow",
            provider_task_id="stage-task-slow",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    async def fake_sync_image_task(db_session, task_id):
        task = db_session.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).one()
        task.status = "running"
        db_session.commit()
        db_session.refresh(task)
        return task

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service.sync_image_task", fake_sync_image_task)
    monkeypatch.setattr(reference_asset_service, "REFERENCE_SYNC_POLL_ATTEMPTS", 1)
    monkeypatch.setattr(reference_asset_service, "REFERENCE_SYNC_POLL_DELAY_SECONDS", 0)

    with pytest.raises(reference_asset_service.ReferenceAssetError) as exc_info:
        await reference_asset_service.generate_reference_url(db, "reference prompt")

    assert exc_info.value.code == "REFERENCE_PROVIDER_STILL_RUNNING"
    assert exc_info.value.details["status"] == "running"


@pytest.mark.asyncio
async def test_generate_reference_url_reuses_running_task_for_same_reference_slot(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    existing = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        prompt="old prompt before timeout",
        destination_role="character_anchor_image",
        destination_context_json={
            "asset_type": "character",
            "asset_id": "character-1",
            "slot": "avatar_front_url",
        },
        pixelle_task_id="stage-task-existing",
        provider_task_id="stage-task-existing",
    )
    db.add(existing)
    db.commit()
    db.refresh(existing)

    async def fake_create_image_task(db_session, payload):
        raise AssertionError("same reference slot should reuse the running task")

    sync_calls = []

    async def fake_sync_image_task(db_session, task_id):
        sync_calls.append(task_id)
        task = db_session.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).one()
        db_session.add(ImageCreationAsset(
            task_id=task.id,
            url="http://127.0.0.1:8000/static/image-creation/outputs/reused-reference.png",
            status="approved",
            slot_key="default",
            storage_status="persisted",
        ))
        task.status = "completed"
        db_session.commit()
        db_session.refresh(task)
        return task

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service.sync_image_task", fake_sync_image_task)
    monkeypatch.setattr(reference_asset_service, "REFERENCE_SYNC_POLL_ATTEMPTS", 1)
    monkeypatch.setattr(reference_asset_service, "REFERENCE_SYNC_POLL_DELAY_SECONDS", 0)

    url = await reference_asset_service.generate_reference_url(
        db,
        "new prompt after timeout",
        destination_role="character_anchor_image",
        destination_context={
            "asset_type": "character",
            "asset_id": "character-1",
            "slot": "avatar_front_url",
        },
    )

    assert url == "http://127.0.0.1:8000/static/image-creation/outputs/reused-reference.png"
    assert sync_calls == [existing.id]
    assert db.query(ImageCreationTask).count() == 1


@pytest.mark.asyncio
async def test_generate_reference_url_downloads_external_provider_asset_into_project(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    async def fake_create_image_task(db_session, payload):
        task = ImageCreationTask(
            mode="text_to_image",
            output_mode="single",
            capability_key="text_to_image",
            status="running",
            prompt=payload["prompt"],
            provider_task_id="provider-task-1",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    async def fake_sync_image_task(db_session, task_id):
        task = db_session.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).one()
        db_session.add(ImageCreationAsset(
            task_id=task.id,
            url="https://provider.test/reference.png",
            status="review_pending",
            slot_key="default",
            storage_status="registered",
        ))
        task.status = "completed"
        db_session.commit()
        db_session.refresh(task)
        return task

    async def fake_copy_external_image(url):
        assert url == "https://provider.test/reference.png"
        return {
            "url": "http://127.0.0.1:8000/static/image-creation/outputs/copied.png",
            "local_path": "D:\\devWorkspace\\jsProjects\\dy_auto\\server\\app\\static\\image-creation\\outputs\\copied.png",
            "storage_path": "outputs/copied.png",
            "checksum": "copied-checksum",
            "size_bytes": 1234,
            "mime_type": "image/png",
        }

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service.sync_image_task", fake_sync_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service._copy_external_image", fake_copy_external_image)

    url = await reference_asset_service.generate_reference_url(
        db,
        "reference prompt",
        destination_role="character_anchor_image",
        destination_context={"asset_type": "character", "slot": "avatar_front_url"},
    )

    assert url == "http://127.0.0.1:8000/static/image-creation/outputs/copied.png"
    asset = db.query(ImageCreationAsset).one()
    assert asset.url == "http://127.0.0.1:8000/static/image-creation/outputs/copied.png"
    assert asset.source_url == "https://provider.test/reference.png"
    assert asset.storage_path == "outputs/copied.png"
    assert asset.local_path.endswith("outputs\\copied.png")
    assert asset.checksum == "copied-checksum"
    assert asset.size_bytes == 1234
    assert asset.mime_type == "image/png"
    assert asset.storage_status == "persisted"


@pytest.mark.asyncio
async def test_generate_reference_url_copies_provider_url_that_looks_like_static_path(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    source_url = "https://provider.test/static/image-creation/outputs/reference.png"

    async def fake_create_image_task(db_session, payload):
        task = ImageCreationTask(
            mode="text_to_image",
            output_mode="single",
            capability_key="text_to_image",
            status="running",
            prompt=payload["prompt"],
            provider_task_id="provider-task-1",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    async def fake_sync_image_task(db_session, task_id):
        task = db_session.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).one()
        db_session.add(ImageCreationAsset(
            task_id=task.id,
            url=source_url,
            status="review_pending",
            slot_key="default",
            storage_status="registered",
        ))
        task.status = "completed"
        db_session.commit()
        db_session.refresh(task)
        return task

    copied = []

    async def fake_copy_external_image(url):
        copied.append(url)
        return {
            "url": "http://127.0.0.1:8000/static/image-creation/outputs/copied-static-path.png",
            "local_path": "D:\\devWorkspace\\jsProjects\\dy_auto\\server\\app\\static\\image-creation\\outputs\\copied-static-path.png",
            "storage_path": "outputs/copied-static-path.png",
            "checksum": "copied-static-path-checksum",
            "size_bytes": 1234,
            "mime_type": "image/png",
        }

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service.sync_image_task", fake_sync_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service._copy_external_image", fake_copy_external_image)

    url = await reference_asset_service.generate_reference_url(db, "reference prompt")

    assert copied == [source_url]
    assert url == "http://127.0.0.1:8000/static/image-creation/outputs/copied-static-path.png"


@pytest.mark.asyncio
async def test_generate_reference_url_wraps_project_copy_filesystem_error(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    async def fake_create_image_task(db_session, payload):
        task = ImageCreationTask(
            mode="text_to_image",
            output_mode="single",
            capability_key="text_to_image",
            status="running",
            prompt=payload["prompt"],
            provider_task_id="provider-task-1",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    async def fake_sync_image_task(db_session, task_id):
        task = db_session.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).one()
        db_session.add(ImageCreationAsset(
            task_id=task.id,
            url="https://provider.test/reference.png",
            status="review_pending",
            slot_key="default",
            storage_status="registered",
        ))
        task.status = "completed"
        db_session.commit()
        db_session.refresh(task)
        return task

    async def fake_copy_external_image(url):
        raise OSError("disk full")

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service.sync_image_task", fake_sync_image_task)
    monkeypatch.setattr("app.domains.image_generation.image_creation_service._copy_external_image", fake_copy_external_image)

    with pytest.raises(reference_asset_service.ReferenceAssetError) as exc_info:
        await reference_asset_service.generate_reference_url(db, "reference prompt")

    assert exc_info.value.code == "REFERENCE_PROVIDER_PERSIST_FAILED"
    assert exc_info.value.details["source_url"] == "https://provider.test/reference.png"


@pytest.mark.asyncio
async def test_image_creation_http_error_wraps_as_reference_provider_request_failed(db, monkeypatch):
    from app.domains.creative_library import reference_asset_service
    from fastapi import HTTPException

    async def fake_create_image_task(db_session, payload):
        raise HTTPException(status_code=502, detail={
            "error_code": "PIXELLE_IMAGE_SUBMIT_FAILED",
            "message": "provider rejected prompt",
        })

    monkeypatch.setattr("app.domains.image_generation.image_creation_service.create_image_task", fake_create_image_task)

    with pytest.raises(reference_asset_service.ReferenceAssetError) as exc_info:
        await reference_asset_service.generate_reference_url(db, "prompt")

    assert exc_info.value.code == "REFERENCE_PROVIDER_REQUEST_FAILED"
    assert exc_info.value.message == "provider rejected prompt"
    assert exc_info.value.details["provider_code"] == "PIXELLE_IMAGE_SUBMIT_FAILED"
