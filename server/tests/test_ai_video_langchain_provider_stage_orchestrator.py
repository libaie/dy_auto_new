import json

import pytest

from app.config import bj_now
from app.db.models import Episode, ProductionJob, ProductionPlan, Series, VideoProductionRun
from app.domains.ai_video_series.langchain_runtime.provider_stage_orchestrator import (
    run_provider_stage_agent,
)
from app.domains.video_production.production_action_result import ProductionActionResult


class CapturingRunner:
    def __init__(self):
        self.calls = []

    async def run_json(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "ok"}


@pytest.mark.parametrize(
    ("job_stage", "expected_tools"),
    [
        ("image_generation", ["submit_image_generation", "query_image_task"]),
        ("video_generation", ["submit_video_generation", "query_video_task"]),
        ("episode_compose", ["submit_compose", "query_compose_task"]),
        ("composition", ["submit_compose", "query_compose_task"]),
    ],
)
@pytest.mark.asyncio
async def test_provider_stage_agent_gets_stage_tools_and_prompt_fields(db, job_stage, expected_tools):
    runner = CapturingRunner()
    runtime_config = {"provider": "mock", "api_key": "sentinel-secret-123"}

    result = await run_provider_stage_agent(
        db,
        run_id="run-1",
        job_id="job-1",
        job_stage=job_stage,
        runtime_config=runtime_config,
        agent_runner=runner,
    )

    assert result == {"status": "ok"}
    call = runner.calls[0]
    assert [tool.name for tool in call["tools"]] == expected_tools
    assert call["runtime_config"] == runtime_config
    assert "sentinel-secret-123" not in call["system_prompt"]
    assert "sentinel-secret-123" not in call["user_prompt"]
    assert "Call the submit tool first with run_id and job_id." in call["system_prompt"]
    assert json.loads(call["user_prompt"]) == {
        "run_id": "run-1",
        "job_id": "job-1",
        "job_stage": job_stage,
        "allowed_tools": expected_tools,
    }


@pytest.mark.asyncio
async def test_provider_stage_agent_runs_mock_tools_directly_without_runner(db, monkeypatch):
    series = Series(title="Provider Direct", logline="Provider Direct", genre="drama")
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
        production_plan_id=plan.id,
        status="image_batch_running",
        current_stage="image_generation",
    )
    db.add(run)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id="segment-1",
        stage="image_generation",
        status="queued",
        idempotency_key="provider-direct:segment-1:image:v1",
        scheduled_at=bj_now(),
    )
    db.add(job)
    db.commit()
    calls = []

    async def fake_execute_provider_job(db_arg, run_arg, job_arg):
        calls.append(job_arg.id)
        assets = [] if len(calls) == 1 else [{"url": "https://cdn.test/image.png"}]
        return ProductionActionResult.success(
            "provider step",
            data={
                "provider_result": {
                    "provider_stage_task_id": "stage-task-1",
                    "provider_task_id": "provider-task-1",
                    "status": "completed",
                    "assets": assets,
                }
            },
        )

    monkeypatch.setattr(
        "app.domains.ai_video_series.langchain_runtime.provider_tools._execute_provider_job",
        fake_execute_provider_job,
    )

    result = await run_provider_stage_agent(
        db,
        run_id=run.id,
        job_id=job.id,
        job_stage="image_generation",
        runtime_config={"provider": "mock"},
        agent_runner=None,
    )

    assert calls == [job.id, job.id]
    assert result["status"] == "success"
    assert result["provider_stage_task_id"] == "stage-task-1"
    assert result["asset_count"] == 1

@pytest.mark.asyncio
async def test_unsupported_provider_stage_raises_value_error(db):
    with pytest.raises(ValueError, match="Unsupported provider agent stage: storyboard"):
        await run_provider_stage_agent(
            db,
            run_id="run-1",
            job_id="job-1",
            job_stage="storyboard",
            runtime_config={},
            agent_runner=CapturingRunner(),
        )
