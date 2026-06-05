import pytest

from app.services.pixelle_stage_client import submit_image_batch, get_stage_task, submit_image_create


@pytest.mark.asyncio
async def test_submit_image_batch_calls_pixelle_stage_api(monkeypatch):
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-1", "assets": []}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    result = await submit_image_batch(
        db=None,
        run_id="run-1",
        episode_id="episode-1",
        frames=[{"frame_id": "frame-001", "image_prompt": "prompt", "reference_urls": [], "duration": 5}],
        model_config={"provider": "mock", "api_key": "secret"},
    )

    assert result["stage_task_id"] == "stage-1"
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/stages/images/batch"
    assert calls[0][1] != "/api/stages/images/create"
    assert calls[0][2]["external_run_id"] == "run-1"


@pytest.mark.asyncio
async def test_submit_image_create_calls_pixelle_stage_api(monkeypatch):
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-create-1", "assets": []}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    result = await submit_image_create(
        db=None,
        external_task_id="image-task-1",
        mode="text_to_image",
        capability_key="seedream",
        output_mode="single",
        prompt="cinematic frame",
        negative_prompt="blur",
        source_image_url="https://cdn.test/source.png",
        reference_images=[{"url": "https://cdn.test/ref.png", "role": "style"}],
        count=2,
        size="1024x1024",
        output_format="png",
        response_format="url",
        provider_options={"watermark": False},
        model_config={"provider": "mock", "api_key": "secret"},
        context={"group_id": "group-1"},
    )

    assert result["stage_task_id"] == "stage-create-1"
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/stages/images/create"
    payload = calls[0][2]
    assert payload["external_task_id"] == "image-task-1"
    assert payload["mode"] == "text_to_image"
    assert payload["model_config"] == {"provider": "mock", "api_key": "secret"}


@pytest.mark.asyncio
async def test_submit_image_create_requires_model_config():
    with pytest.raises(ValueError, match="submit_image_create requires a non-empty model_config"):
        await submit_image_create(
            db=None,
            external_task_id="image-task-1",
            mode="text_to_image",
            capability_key="seedream",
            output_mode="single",
            prompt="cinematic frame",
            model_config={},
        )


@pytest.mark.asyncio
async def test_get_stage_task_calls_pixelle_status(monkeypatch):
    async def fake_request(method, path, db=None, **kwargs):
        return {"ok": True, "stage_task_id": "stage-1", "status": "completed", "assets": []}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    result = await get_stage_task(None, "stage-1")

    assert result["status"] == "completed"
