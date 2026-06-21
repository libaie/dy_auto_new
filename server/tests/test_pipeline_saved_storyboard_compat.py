import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import AgencyExpertInvocation, AIModel, Episode, PipelineRun, Series
from app.domains.agency_operations.agency_runtime import AgencyRuntimeResult
from app.domains.system_configuration.crypto import encrypt


client = TestClient(app)


def _series_with_storyboard(db):
    series = Series(
        title="Pipeline Compat",
        logline="Saved storyboard should start without director_plan.",
        genre="drama",
        target_duration=60,
        mode="fully_automatic",
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
                "narration": "A clean opening.",
                "image_prompt": "A cinematic opening frame.",
                "duration": 5,
                "reference_urls": ["https://cdn.test/ref.png"],
            }]
        },
    )
    db.add(episode)
    db.commit()
    return series, episode


def _expert_review_model(db):
    model = AIModel(
        name="Pipeline Expert Review",
        model_type="llm",
        provider="openai-compatible",
        base_url="https://llm.test/v1",
        api_key=encrypt("expert-key"),
        model_name="expert-review-model",
        enabled=True,
        config_json={
            "scene_key": "llm_agency_expert_review",
            "protocol": "openai_chat_completions",
        },
    )
    db.add(model)
    db.commit()
    return model


async def _agency_pass(self, **kwargs):
    return AgencyRuntimeResult(
        result_status="passed",
        output_summary={
            "decision": f"{kwargs['stage']} passed",
            "findings": [],
            "recommendations": [],
            "required_changes": [],
            "scorecard": {
                "overall_score": 95,
                "pass_threshold": 80,
                "verdict": "pass",
                "dimensions": [{"key": "quality", "score": 95, "threshold": 80}],
                "repair_intent": "none",
                "confidence": 0.9,
            },
        },
        evidence=[],
        token_usage={},
        model_config_snapshot={"provider": "test"},
    )


@pytest.mark.asyncio
async def test_pipeline_start_blocks_when_expert_review_model_missing(db):
    series, episode = _series_with_storyboard(db)

    resp = client.post("/api/pipeline/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "director_plan": None,
    })

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "EXPERT_MODEL_CONFIG_MISSING"
    assert detail["stage"] == "storyboard"
    assert detail["run_id"]
    run = db.query(PipelineRun).filter_by(id=detail["run_id"]).one()
    assert run.status == "blocked"
    assert run.layers_json["1"]["agency_trace"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"


@pytest.mark.asyncio
async def test_pipeline_start_blocks_provider_rendering_without_production_job(db, monkeypatch):
    series, episode = _series_with_storyboard(db)
    _expert_review_model(db)
    monkeypatch.setattr("app.domains.agency_operations.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)

    resp = client.post("/api/pipeline/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "director_plan": None,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Script pipeline provider rendering requires a production run job."
    run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    assert run.status == "blocked"
    assert run.layers_json["0"]["status"] == "blocked"
    assert run.layers_json["0"]["error"] == "Script pipeline provider rendering requires a production run job."
    assert run.layers_json["1"]["agency_trace_status"] == "complete"
    run_id = run.id
    invocations = db.query(AgencyExpertInvocation).filter_by(pipeline_run_id=run_id).all()
    assert invocations
    assert {item.stage for item in invocations} == {"storyboard"}


def test_pipeline_run_lookup_routes_exist(db):
    series, episode = _series_with_storyboard(db)
    run = PipelineRun(
        series_id=series.id,
        episode_id=episode.id,
        mode="fully_automatic",
        status="running",
        current_layer=0,
        layers_json={"0": {"status": "queued"}},
    )
    db.add(run)
    db.commit()

    by_series = client.get(f"/api/pipeline/runs/{series.id}")
    by_pair = client.get(f"/api/pipeline/runs/{series.id}/{run.id}")
    by_id = client.get(f"/api/pipeline/runs/by-id/{run.id}")

    assert by_series.status_code == 200
    assert by_pair.status_code == 200
    assert by_id.status_code == 200
    assert by_id.json()["run"]["id"] == run.id
    assert by_id.json()["run"]["agency_trace_status"] == "missing"
