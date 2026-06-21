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
    assert (
        "Call each tool named in required_sequence in order with run_id and job_id, "
        "then return the final tool result as a JSON object."
    ) in call["system_prompt"]
    assert json.loads(call["user_prompt"]) == {
        "run_id": "run-1",
        "job_id": "job-1",
        "job_stage": job_stage,
        "required_sequence": expected_tools,
    }


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
