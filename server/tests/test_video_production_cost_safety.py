import pytest
from fastapi.testclient import TestClient

from app.db_models import Episode, ProductionPlan, Series, VideoProductionRun
from app.main import app
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.production_run_service import start_episode_production
from app.services.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E


client = TestClient(app)


def _one_sentence_payload(**overrides):
    payload = {
        "prompt": "A detective finds a hidden signal inside an old radio broadcast.",
        "title": "Signal",
        "genre": "mystery",
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
        "run_type": REAL_SHORT_E2E,
    }
    payload.update(overrides)
    return payload


def _counts(db):
    return {
        "series": db.query(Series).count(),
        "plans": db.query(ProductionPlan).count(),
        "runs": db.query(VideoProductionRun).count(),
    }


def _series_with_episode(db):
    series = Series(
        title="Budget Guard",
        logline="Guard before mutation",
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
    db.commit()
    return series, episode


def test_one_sentence_real_short_zero_budget_fails_before_db_mutation(db):
    before = _counts(db)

    response = client.post(
        "/api/video-production/one-sentence",
        json=_one_sentence_payload(budget_limit=0),
    )

    assert response.status_code in {400, 409}
    assert response.json()["detail"]["code"] == "BUDGET_EXCEEDED"
    assert response.json()["detail"]["repair_route"] == "/one-sentence-video"
    assert _counts(db) == before


def test_one_sentence_real_short_missing_budget_fails_before_db_mutation(db):
    before = _counts(db)
    payload = _one_sentence_payload()
    payload.pop("budget_limit")

    response = client.post("/api/video-production/one-sentence", json=payload)

    assert response.status_code in {400, 409}
    assert response.json()["detail"]["code"] == "BUDGET_EXCEEDED"
    assert response.json()["detail"]["repair_route"] == "/one-sentence-video"
    assert _counts(db) == before


def test_one_sentence_mock_scale_accepts_zero_budget(db):
    response = client.post(
        "/api/video-production/one-sentence",
        json=_one_sentence_payload(
            budget_limit=0,
            run_type=MOCK_SERIES_SCALE,
            target_duration_seconds=240 * 60,
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["run_type"] == MOCK_SERIES_SCALE
    assert body["run"]["model_trace_json"]["provider_calls"] == 0


@pytest.mark.asyncio
async def test_start_episode_production_real_short_zero_budget_fails_before_plan_or_run_mutation(db):
    series, episode = _series_with_episode(db)
    before = _counts(db)

    with pytest.raises(ProductionRepairableError) as exc_info:
        await start_episode_production(
            db,
            series_id=series.id,
            episode_id=episode.id,
            budget_limit=0,
            autostart_images=False,
            run_type=REAL_SHORT_E2E,
        )

    assert exc_info.value.code == ProductionErrorCode.BUDGET_EXCEEDED
    assert _counts(db) == before


@pytest.mark.asyncio
async def test_start_episode_production_real_short_missing_budget_fails_before_plan_or_run_mutation(db):
    series, episode = _series_with_episode(db)
    before = _counts(db)

    with pytest.raises(ProductionRepairableError) as exc_info:
        await start_episode_production(
            db,
            series_id=series.id,
            episode_id=episode.id,
            target_duration_seconds=60,
            autostart_images=False,
            run_type=REAL_SHORT_E2E,
        )

    assert exc_info.value.code == ProductionErrorCode.BUDGET_EXCEEDED
    assert _counts(db) == before
