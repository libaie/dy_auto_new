import pytest
from fastapi.testclient import TestClient

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.main import app
from app.services.agency_multimodal_review import build_multimodal_asset_context, run_multimodal_asset_review


def _asset(db, *, asset_type="image", thumbnail_url=None):
    series = Series(title="Multimodal", logline="One line", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={
            "frames": [{
                "frame_id": "shot-001",
                "image_prompt": "original image prompt",
                "video_prompt": "original video prompt",
            }]
        },
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, storyboard_json=episode.storyboard_json)
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="shot-001",
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url="https://cdn.test/shot.png" if asset_type == "image" else "https://cdn.test/shot.mp4",
        thumbnail_url=thumbnail_url if thumbnail_url is not None else ("https://cdn.test/shot-thumb.png" if asset_type != "image" else None),
        status="review_pending",
        version=1,
    )
    db.add(asset)
    db.commit()
    return series, episode, run, asset


def test_build_multimodal_asset_context_includes_real_asset_and_prompt(db):
    _, _, _, asset = _asset(db)

    context = build_multimodal_asset_context(db, asset.id)

    assert context["asset"]["url"] == "https://cdn.test/shot.png"
    assert context["asset_review"]["media_inputs"] == [{"type": "image_url", "url": "https://cdn.test/shot.png"}]
    assert context["storyboard_frame"]["image_prompt"] == "original image prompt"
    assert context["asset_review"]["original_prompt"] == "original image prompt"


@pytest.mark.asyncio
async def test_run_multimodal_asset_review_dispatches_image_review(db, monkeypatch):
    _, _, run, asset = _asset(db)
    captured = {}

    def fake_config(db_arg, scene_key):
        captured["scene_key"] = scene_key
        return {"provider": "openai", "base_url": "https://model.test/v1", "api_key": "key", "model": "qwen-vl"}

    async def fake_review(self, db_arg, **kwargs):
        captured["kwargs"] = kwargs
        return {"stage": "image_review", "stage_status": "passed", "invocation_ids": ["inv-1"], "invocations": []}

    monkeypatch.setattr("app.services.agency_multimodal_review.resolve_runtime_model_config", fake_config)
    monkeypatch.setattr("app.services.agency_multimodal_review.AgencyOrchestrator.run_image_review", fake_review)

    trace = await run_multimodal_asset_review(db, asset.id)

    assert trace["stage"] == "image_review"
    assert captured["scene_key"] == "llm_agency_expert_review"
    assert captured["kwargs"]["run_id"] == run.id
    assert captured["kwargs"]["stage_context"]["asset_review"]["media_inputs"][0]["url"] == "https://cdn.test/shot.png"


@pytest.mark.asyncio
async def test_run_multimodal_asset_review_dispatches_video_review(db, monkeypatch):
    _, _, _, asset = _asset(db, asset_type="video_segment")
    captured = {}

    monkeypatch.setattr(
        "app.services.agency_multimodal_review.resolve_runtime_model_config",
        lambda db_arg, scene_key: {"provider": "openai", "base_url": "https://model.test/v1", "api_key": "key", "model": "qwen-vl"},
    )

    async def fake_review(self, db_arg, **kwargs):
        captured["kwargs"] = kwargs
        return {"stage": "video_review", "stage_status": "warn", "invocation_ids": ["inv-2"], "invocations": []}

    monkeypatch.setattr("app.services.agency_multimodal_review.AgencyOrchestrator.run_video_review", fake_review)

    trace = await run_multimodal_asset_review(db, asset.id)

    assert trace["stage"] == "video_review"
    assert captured["kwargs"]["stage_context"]["asset_review"]["original_prompt"] == "original video prompt"
    assert captured["kwargs"]["stage_context"]["asset_review"]["media_inputs"] == [
        {"type": "video_url", "url": "https://cdn.test/shot.mp4"},
        {"type": "image_url", "url": "https://cdn.test/shot-thumb.png"},
    ]


@pytest.mark.asyncio
async def test_run_multimodal_asset_review_sends_video_url_without_thumbnail(db, monkeypatch):
    _, _, _, asset = _asset(db, asset_type="video_segment", thumbnail_url="")
    captured = {}

    monkeypatch.setattr(
        "app.services.agency_multimodal_review.resolve_runtime_model_config",
        lambda db_arg, scene_key: {"provider": "openai", "base_url": "https://model.test/v1", "api_key": "key", "model": "qwen-vl"},
    )

    async def fake_review(self, db_arg, **kwargs):
        captured["kwargs"] = kwargs
        return {"stage": "video_review", "stage_status": "warn", "invocation_ids": ["inv-2"], "invocations": []}

    monkeypatch.setattr("app.services.agency_multimodal_review.AgencyOrchestrator.run_video_review", fake_review)

    await run_multimodal_asset_review(db, asset.id)

    assert captured["kwargs"]["stage_context"]["asset_review"]["media_inputs"] == [
        {"type": "video_url", "url": "https://cdn.test/shot.mp4"}
    ]


def test_multimodal_review_route_returns_trace(db, monkeypatch):
    _, _, _, asset = _asset(db)
    client = TestClient(app)

    async def fake_review(db_arg, asset_id):
        assert asset_id == asset.id
        return {"stage": "image_review", "stage_status": "passed"}

    monkeypatch.setattr("app.services.agency_multimodal_review.run_multimodal_asset_review", fake_review)

    response = client.post(f"/api/agency/assets/{asset.id}/multimodal-review")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "trace": {"stage": "image_review", "stage_status": "passed"}}
