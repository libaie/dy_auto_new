import pytest
from fastapi.testclient import TestClient

from app.db.models import Character, Episode, Scene, Series, VideoProductionRun
from app.main import app
from app.domains.video_production.production_errors import ProductionRepairableError
from app.domains.video_production.production_run_service import start_episode_production
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E
from app.domains.video_production.video_production_service import start_image_stage


client = TestClient(app)


def _payload(**overrides):
    payload = {
        "prompt": "A detective finds a hidden signal inside an old radio broadcast.",
        "title": "Signal",
        "genre": "mystery",
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
    }
    payload.update(overrides)
    return payload


def _counts(db):
    return {
        "series": db.query(Series).count(),
        "runs": db.query(VideoProductionRun).count(),
    }


async def _fake_character_references(db, character_id, slot="all"):
    character = db.query(Character).filter_by(id=character_id).one()
    character.avatar_front_url = "/static/image-creation/character-front.png"
    db.commit()
    return {"ok": True, "generated": [{"slot": "avatar_front_url", "url": character.avatar_front_url}]}


async def _fake_scene_references(db, scene_id, slot="all"):
    scene = db.query(Scene).filter_by(id=scene_id).one()
    scene.reference_wideshot_url = "/static/image-creation/scene-wide.png"
    db.commit()
    return {"ok": True, "generated": [{"slot": "reference_wideshot_url", "url": scene.reference_wideshot_url}]}


def _mock_reference_generation(monkeypatch):
    monkeypatch.setattr(
        "app.domains.creative_library.reference_asset_service.generate_character_reference_images",
        _fake_character_references,
    )
    monkeypatch.setattr(
        "app.domains.creative_library.reference_asset_service.generate_scene_reference_images",
        _fake_scene_references,
    )


def _mock_scale_run(db):
    series = Series(
        title="Mock Scale",
        logline="Provider guard",
        genre="drama",
        story_bible_json={"style_lock": {"locked": True}},
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "image_prompt": "Image prompt",
                "video_prompt": "Video prompt",
                "duration": 5,
            }]
        },
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=MOCK_SERIES_SCALE,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    return run


def test_real_short_e2e_rejects_duration_below_minimum_before_db_write(db):
    before = _counts(db)

    resp = client.post(
        "/api/video-production/one-sentence",
        json=_payload(target_duration_seconds=4, run_type=REAL_SHORT_E2E),
    )

    assert resp.status_code == 422
    assert _counts(db) == before


def test_one_sentence_rejects_unknown_run_type_before_db_write(db):
    before = _counts(db)

    resp = client.post(
        "/api/video-production/one-sentence",
        json=_payload(run_type="unknown"),
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_RUN_TYPE"
    assert resp.json()["detail"]["error_code"] == "INVALID_RUN_TYPE"
    assert resp.json()["detail"]["repair_route"] == "/one-sentence-video"
    assert _counts(db) == before


def test_real_short_e2e_rejects_duration_above_materialized_contract_before_db_write(db):
    before = _counts(db)

    resp = client.post(
        "/api/video-production/one-sentence",
        json=_payload(target_duration_seconds=961, run_type=REAL_SHORT_E2E),
    )

    assert resp.status_code == 400
    assert "no more than 960 seconds" in resp.json()["detail"]
    assert _counts(db) == before


def test_one_sentence_success_response_exposes_real_short_e2e_run_type(db, monkeypatch):
    _mock_reference_generation(monkeypatch)

    resp = client.post(
        "/api/video-production/one-sentence",
        json=_payload(target_duration_seconds=60),
    )

    assert resp.status_code == 200
    assert resp.json()["run"]["run_type"] == REAL_SHORT_E2E


def test_one_sentence_accepts_mock_series_scale_without_real_short_duration_guard(db):
    resp = client.post(
        "/api/video-production/one-sentence",
        json=_payload(run_type=MOCK_SERIES_SCALE, target_duration_seconds=240 * 60),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["run_type"] == MOCK_SERIES_SCALE
    assert body["run"]["model_trace_json"]["provider_calls"] == 0
    assert body["run"]["production_plan_id"]


@pytest.mark.asyncio
async def test_mock_series_scale_cannot_enter_real_provider_image_stage(db, monkeypatch):
    run = _mock_scale_run(db)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("mock_series_scale entered provider stage")

    monkeypatch.setattr("app.domains.video_production.video_production_service._guard_provider_stage", fail_if_called)

    with pytest.raises(Exception) as exc_info:
        await start_image_stage(db, run.id)

    assert "mock_series_scale" in str(exc_info.value)


@pytest.mark.asyncio
async def test_real_short_image_stage_blocks_empty_reference_payload_before_provider(db, monkeypatch):
    series = Series(
        title="Missing Refs",
        logline="Test",
        genre="drama",
        target_duration=60,
        story_bible_json={"style_lock": {"locked": True, "version": 1}},
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-empty-ref",
                "scene_id": "scene-1",
                "character_ids": ["character-1"],
                "image_prompt": "Image prompt",
                "video_prompt": "Video prompt",
                "duration": 60,
                "reference_urls": [],
            }],
        },
    )
    db.add(episode)
    db.commit()

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("provider guard should not run before local reference validation")

    monkeypatch.setattr("app.domains.video_production.video_production_service._guard_provider_stage", fail_if_called)

    run = await start_episode_production(
        db,
        series_id=series.id,
        episode_id=episode.id,
        target_duration_seconds=60,
        budget_limit=1,
        autostart_images=False,
        run_type=REAL_SHORT_E2E,
        prepare_text_artifacts=False,
    )

    with pytest.raises(ProductionRepairableError) as exc_info:
        await start_image_stage(db, run.id)

    assert exc_info.value.code.value == "REVIEW_GATE_BLOCKED"
    assert "reference" in exc_info.value.message.lower()
    assert exc_info.value.affected_ids
