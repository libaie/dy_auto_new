import pytest

from app.domains.video_production import production_worker_service as worker


@pytest.mark.asyncio
async def test_execute_real_job_uses_provider_stage_agent(monkeypatch, db):
    calls = []

    async def fake_agent(db_arg, *, run_id, job_id, job_stage, runtime_config, agent_runner=None):
        calls.append((db_arg, run_id, job_id, job_stage, runtime_config["provider"]))
        return {"status": "success", "message": "done", "asset_count": 1}

    class FailDirectExecutor:
        async def execute(self, *args, **kwargs):
            raise AssertionError("execute_real_job should route real provider jobs through the agent")

    async def no_gate(*args, **kwargs):
        return None

    monkeypatch.setattr(worker, "run_provider_stage_agent", fake_agent, raising=False)
    monkeypatch.setattr(worker, "_job_spec", lambda db_arg, run, job: {"scene_key": "image_generation", "payload": {}})
    monkeypatch.setattr(worker, "_run_deferred_stage_gates", no_gate)
    monkeypatch.setattr(worker, "ProviderStageExecutor", lambda adapter: FailDirectExecutor())
    monkeypatch.setattr(
        worker,
        "resolve_runtime_model_config",
        lambda db_arg, scene_key: {"provider": "mock", "model": scene_key},
    )
    run = type("Run", (), {"id": "run-1", "episode_id": "episode-1", "production_plan_id": "plan-1"})()
    job = type(
        "Job",
        (),
        {"id": "job-1", "stage": "image_generation", "target_type": "frame", "target_id": "frame-1"},
    )()

    result = await worker.execute_real_job(db, run, job)

    assert result.status == "success"
    assert result.data["status"] == "success"
    assert calls == [(db, "run-1", "job-1", "image_generation", "mock")]
