import pytest

from app.db.models import Episode, ProductionPlan, ProviderStageTask, Series, VideoProductionRun
from app.domains.pixelle_integration.pixelle_stage_client import (
    _compose_segments_with_ffmpeg,
    get_stage_task,
    submit_image_batch,
    submit_image_create,
    submit_compose,
    submit_video_batch,
)


@pytest.mark.asyncio
async def test_submit_image_batch_calls_pixelle_stage_api(monkeypatch):
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-1", "assets": []}

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fake_request)

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
async def test_submit_image_batch_uses_dashscope_multimodal_generation(monkeypatch):
    calls = []

    async def fail_pixelle(*args, **kwargs):
        raise AssertionError("dashscope image models must not call Pixelle")

    async def fake_dashscope(method, base_url, path, api_key, request_kwargs):
        calls.append((method, base_url, path, api_key, request_kwargs))
        return {
            "request_id": "request-1",
            "output": {
                "choices": [{
                    "message": {"content": [{"image": "https://cdn.test/generated.png"}]},
                }],
            },
            "usage": {"image_count": 1},
        }

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fail_pixelle)
    monkeypatch.setattr(
        "app.domains.pixelle_integration.pixelle_stage_client._dashscope_request",
        fake_dashscope,
        raising=False,
    )

    result = await submit_image_batch(
        db=None,
        run_id="run-1",
        episode_id="episode-1",
        frames=[{
            "frame_id": "frame-001",
            "production_segment_id": "segment-1",
            "image_prompt": "cinematic seed on a rooftop",
            "duration": 5,
        }],
        model_config={
            "provider": "wan",
            "model": "wan2.6-image",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "api_key": "test-key",
            "config": {
                "protocol": "dashscope_multimodal_generation",
                "task_path": "/services/aigc/multimodal-generation/generation",
                "default_size": "1024*1024",
            },
        },
        provider_stage_task_id="stage-task-1",
    )

    assert result["provider_task_id"] == "stage-task-1"
    assert result["status"] == "succeeded"
    assert result["assets"][0]["url"] == "https://cdn.test/generated.png"
    assert result["assets"][0]["production_segment_id"] == "segment-1"
    assert calls[0][0] == "POST"
    assert calls[0][2] == "/services/aigc/multimodal-generation/generation"
    assert calls[0][4]["json"]["model"] == "wan2.6-image"

    synced = await get_stage_task(None, "stage-task-1")

    assert synced["status"] == "succeeded"
    assert synced["assets"][0]["url"] == "https://cdn.test/generated.png"


@pytest.mark.asyncio
async def test_submit_image_batch_uses_dashscope_async_image_generation_when_configured(monkeypatch):
    calls = []

    async def fail_pixelle(*args, **kwargs):
        raise AssertionError("dashscope image models must not call Pixelle")

    async def fake_dashscope(method, base_url, path, api_key, request_kwargs):
        calls.append((method, base_url, path, api_key, request_kwargs))
        if method == "POST":
            return {"output": {"task_id": "dashscope-image-1", "task_status": "PENDING"}}
        return {
            "output": {
                "task_id": "dashscope-image-1",
                "task_status": "SUCCEEDED",
                "choices": [{
                    "message": {"content": [{"image": "https://cdn.test/wan-image.png"}]},
                }],
            },
            "usage": {"image_count": 1},
        }

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fail_pixelle)
    monkeypatch.setattr(
        "app.domains.pixelle_integration.pixelle_stage_client._dashscope_request",
        fake_dashscope,
        raising=False,
    )

    result = await submit_image_batch(
        db=None,
        run_id="run-1",
        episode_id="episode-1",
        frames=[{
            "frame_id": "frame-001",
            "production_segment_id": "segment-1",
            "image_prompt": "cinematic seed on a rooftop",
            "duration": 5,
        }],
        model_config={
            "provider": "wan",
            "model": "wan2.6-image",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "api_key": "test-key",
            "config": {
                "protocol": "dashscope_multimodal_generation",
                "task_submit_path": "/services/aigc/image-generation/generation",
                "task_query_path": "/tasks/{task_id}",
                "default_size": "1280*1280",
                "enable_interleave": True,
            },
        },
        provider_stage_task_id="internal-stage-task-1",
    )

    assert result["provider_task_id"] == "dashscope-image-1"
    assert calls[0][0] == "POST"
    assert calls[0][2] == "/services/aigc/image-generation/generation"
    assert calls[0][4]["headers"] == {"X-DashScope-Async": "enable"}
    assert calls[0][4]["json"]["parameters"]["enable_interleave"] is True
    assert calls[0][4]["json"]["parameters"]["max_images"] == 1

    synced = await get_stage_task(None, "dashscope-image-1")

    assert synced["status"] == "succeeded"
    assert synced["assets"][0]["url"] == "https://cdn.test/wan-image.png"
    assert synced["assets"][0]["production_segment_id"] == "segment-1"
    assert synced["assets"][0]["provider_task_id"] == "dashscope-image-1"
    assert synced["assets"][0]["provider_stage_task_id"] == "internal-stage-task-1"
    assert calls[1][0] == "GET"
    assert calls[1][2] == "/tasks/dashscope-image-1"


@pytest.mark.asyncio
async def test_submit_video_batch_uses_dashscope_async_and_get_stage_task_queries(monkeypatch):
    calls = []

    async def fail_pixelle(*args, **kwargs):
        raise AssertionError("dashscope video models must not call Pixelle")

    async def fake_dashscope(method, base_url, path, api_key, request_kwargs):
        calls.append((method, base_url, path, api_key, request_kwargs))
        if method == "POST":
            return {"output": {"task_id": "dashscope-video-1", "task_status": "PENDING"}}
        return {
            "output": {
                "task_id": "dashscope-video-1",
                "task_status": "SUCCEEDED",
                "video_url": "https://cdn.test/video.mp4",
            },
            "usage": {"output_video_duration": 5},
        }

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fail_pixelle)
    monkeypatch.setattr(
        "app.domains.pixelle_integration.pixelle_stage_client._dashscope_request",
        fake_dashscope,
        raising=False,
    )

    result = await submit_video_batch(
        db=None,
        run_id="run-1",
        frames=[{
            "frame_id": "frame-001",
            "production_segment_id": "segment-1",
            "input_image_url": "https://cdn.test/frame.png",
            "video_prompt": "slow push in",
            "duration": 5,
        }],
        model_config={
            "provider": "wan",
            "model": "wan2.7-i2v",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "api_key": "test-key",
            "config": {
                "protocol": "dashscope_async",
                "task_submit_path": "/services/aigc/video-generation/video-synthesis",
                "task_query_path": "/tasks/{task_id}",
                "default_resolution": "720P",
            },
        },
        provider_stage_task_id="internal-video-stage-task-1",
    )

    assert result["provider_task_id"] == "dashscope-video-1"
    assert calls[0][0] == "POST"
    assert calls[0][2] == "/services/aigc/video-generation/video-synthesis"
    assert calls[0][4]["json"]["input"]["media"] == [{
        "type": "first_frame",
        "url": "https://cdn.test/frame.png",
    }]
    assert "img_url" not in calls[0][4]["json"]["input"]

    synced = await get_stage_task(None, "dashscope-video-1")

    assert synced["status"] == "succeeded"
    assert synced["assets"][0]["url"] == "https://cdn.test/video.mp4"
    assert synced["assets"][0]["production_segment_id"] == "segment-1"
    assert synced["assets"][0]["provider_task_id"] == "dashscope-video-1"
    assert synced["assets"][0]["provider_stage_task_id"] == "internal-video-stage-task-1"
    assert calls[1][0] == "GET"
    assert calls[1][2] == "/tasks/dashscope-video-1"


@pytest.mark.asyncio
async def test_submit_compose_uses_local_ffmpeg_protocol(monkeypatch, tmp_path):
    async def fail_pixelle(*args, **kwargs):
        raise AssertionError("local compose must not call Pixelle")

    composed_path = tmp_path / "final.mp4"
    composed_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    def fake_compose_segments(segments, output_path):
        assert [item["video_url"] for item in segments] == ["D:/clips/a.mp4", "D:/clips/b.mp4"]
        assert output_path.name == "internal-compose-stage-task-1.mp4"
        return composed_path

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fail_pixelle)
    monkeypatch.setattr(
        "app.domains.pixelle_integration.pixelle_stage_client._compose_segments_with_ffmpeg",
        fake_compose_segments,
        raising=False,
    )

    result = await submit_compose(
        db=None,
        run_id="run-1",
        segments=[
            {"frame_id": "segment-1", "video_url": "D:/clips/a.mp4", "duration": 5},
            {"frame_id": "segment-2", "video_url": "D:/clips/b.mp4", "duration": 6},
        ],
        edit_manifest={"output_spec": {"resolution": "720p"}},
        model_config={
            "provider": "local",
            "model": "ffmpeg-concat",
            "config": {"protocol": "local_ffmpeg_compose"},
        },
        provider_stage_task_id="internal-compose-stage-task-1",
    )

    assert result["status"] == "succeeded"
    assert result["provider_task_id"] == "internal-compose-stage-task-1"
    assert result["assets"][0]["asset_type"] == "final_video"
    assert result["assets"][0]["local_path"] == str(composed_path)
    assert result["assets"][0]["provider_stage_task_id"] == "internal-compose-stage-task-1"

    synced = await get_stage_task(None, "internal-compose-stage-task-1")

    assert synced["status"] == "succeeded"
    assert synced["assets"][0]["asset_type"] == "final_video"


def test_local_ffmpeg_compose_rejects_paths_outside_controlled_outputs(tmp_path):
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    with pytest.raises(RuntimeError, match="outside allowed output roots"):
        _compose_segments_with_ffmpeg([{"video_url": str(outside)}], tmp_path / "final.mp4")


@pytest.mark.asyncio
async def test_submit_image_create_calls_pixelle_stage_api(monkeypatch):
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-create-1", "assets": []}

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fake_request)

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

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fake_request)

    result = await get_stage_task(None, "stage-1")

    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_get_stage_task_returns_stored_provider_stage_summary_with_internal_task_id(db, monkeypatch):
    async def fail_pixelle(*args, **kwargs):
        raise AssertionError("stored provider stage results must not call Pixelle")

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fail_pixelle)

    series = Series(title="Stored", logline="Stored", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, budget_limit=5.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type="real_short_e2e",
        production_plan_id=plan.id,
        production_link_status="linked",
        status="image_batch_running",
        current_stage="image_generation",
    )
    db.add(run)
    db.flush()
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        target_type="production_segment",
        target_id="segment-1",
        stage="image_generation",
        provider="wan",
        model_name="wan2.6-image",
        request_hash="hash",
        idempotency_key="stored-stage-task",
        status="succeeded",
        provider_task_id="stored-dashscope-image-1",
        response_summary_json={
            "status": "succeeded",
            "provider_task_id": "stored-dashscope-image-1",
            "assets": [{
                "frame_id": "segment-1",
                "production_segment_id": "segment-1",
                "url": "https://cdn.test/image.png",
                "provider_task_id": "stored-dashscope-image-1",
                "provider_stage_task_id": "stored-dashscope-image-1",
            }],
        },
    )
    db.add(task)
    db.commit()

    result = await get_stage_task(db, "stored-dashscope-image-1")

    assert result["status"] == "succeeded"
    assert result["assets"][0]["provider_task_id"] == "stored-dashscope-image-1"
    assert result["assets"][0]["provider_stage_task_id"] == task.id


@pytest.mark.asyncio
async def test_get_stage_task_does_not_return_stored_running_summary(db, monkeypatch):
    calls = []

    async def fake_pixelle(method, path, db=None, **kwargs):
        calls.append((method, path))
        return {"status": "completed", "assets": []}

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fake_pixelle)

    series = Series(title="Running", logline="Running", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, budget_limit=5.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type="real_short_e2e",
        production_plan_id=plan.id,
        production_link_status="linked",
        status="video_batch_running",
        current_stage="video_generation",
    )
    db.add(run)
    db.flush()
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        target_type="production_segment",
        target_id="segment-1",
        stage="video_generation",
        provider="wan",
        model_name="wan2.7-i2v",
        request_hash="hash",
        idempotency_key="stored-running-stage-task",
        status="running",
        provider_task_id="stored-dashscope-video-running",
        response_summary_json={"status": "running", "provider_task_id": "stored-dashscope-video-running"},
    )
    db.add(task)
    db.commit()

    result = await get_stage_task(db, "stored-dashscope-video-running")

    assert result["status"] == "completed"
    assert calls == [("GET", "/api/stages/tasks/stored-dashscope-video-running")]
