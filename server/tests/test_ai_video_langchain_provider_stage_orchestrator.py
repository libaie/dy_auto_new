import json

import pytest

from app.domains.ai_video_series.langchain_runtime.provider_stage_orchestrator import (
    run_provider_stage_agent,
)


class CapturingRunner:
    def __init__(self):
        self.calls = []

    async def run_json(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "ok"}


@pytest.mark.asyncio
async def test_image_generation_agent_gets_only_image_provider_tools(db):
    runner = CapturingRunner()

    result = await run_provider_stage_agent(
        db,
        run_id="run-1",
        job_id="job-image-1",
        job_stage="image_generation",
        runtime_config={"provider": "mock"},
        agent_runner=runner,
    )

    assert result == {"status": "ok"}
    assert [tool.name for tool in runner.calls[0]["tools"]] == [
        "submit_image_generation",
        "query_image_task",
    ]
    user_prompt = json.loads(runner.calls[0]["user_prompt"])
    assert user_prompt["job_id"] == "job-image-1"
    assert user_prompt["required_sequence"] == [
        "submit_image_generation",
        "query_image_task",
    ]


@pytest.mark.asyncio
async def test_episode_compose_agent_gets_compose_provider_tools(db):
    runner = CapturingRunner()

    await run_provider_stage_agent(
        db,
        run_id="run-1",
        job_id="job-compose-1",
        job_stage="episode_compose",
        runtime_config={"provider": "mock"},
        agent_runner=runner,
    )

    assert [tool.name for tool in runner.calls[0]["tools"]] == [
        "submit_compose",
        "query_compose_task",
    ]
    user_prompt = json.loads(runner.calls[0]["user_prompt"])
    assert user_prompt["required_sequence"] == ["submit_compose", "query_compose_task"]


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
