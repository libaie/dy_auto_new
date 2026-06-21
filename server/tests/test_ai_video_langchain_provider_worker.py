import pytest

from app.domains.agency_operations.agency_runtime_contracts import AgencyRuntimeError
from app.domains.video_production import production_worker_service as worker
from app.domains.video_production.production_errors import ProductionErrorCode


@pytest.mark.asyncio
async def test_execute_real_job_uses_provider_stage_agent(monkeypatch, db):
    calls = []

    async def fake_agent(db_arg, *, run_id, job_id, job_stage, runtime_config, agent_runner=None):
        calls.append((db_arg, run_id, job_id, job_stage, runtime_config["provider"]))
        return {
            "status": "success",
            "message": "done",
            "provider_stage_task_id": "pst-1",
            "asset_count": 1,
        }

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


@pytest.mark.asyncio
async def test_execute_real_job_blocks_success_without_provider_evidence(monkeypatch, db):
    async def fake_agent(db_arg, *, run_id, job_id, job_stage, runtime_config, agent_runner=None):
        return {"status": "success", "message": "done"}

    monkeypatch.setattr(worker, "run_provider_stage_agent", fake_agent)
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

    assert result.status == "blocked"
    assert result.code == ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED
    assert result.retryable is True


@pytest.mark.asyncio
async def test_execute_real_job_maps_agent_runtime_error_to_sync_required(monkeypatch, db):
    async def fake_agent(db_arg, *, run_id, job_id, job_stage, runtime_config, agent_runner=None):
        raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "LangChain agent output was not valid JSON.")

    monkeypatch.setattr(worker, "run_provider_stage_agent", fake_agent)
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

    assert result.status == "blocked"
    assert result.code == ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED
    assert result.retryable is True
    assert result.data["error_code"] == "EXPERT_OUTPUT_INVALID_JSON"


@pytest.mark.asyncio
async def test_execute_real_job_restores_structured_agent_blocked_result(monkeypatch, db):
    async def fake_agent(db_arg, *, run_id, job_id, job_stage, runtime_config, agent_runner=None):
        return {
            "status": "blocked",
            "message": "Provider completed with no assets.",
            "code": ProductionErrorCode.PROVIDER_TASK_FAILED.value,
            "error_code": ProductionErrorCode.PROVIDER_TASK_FAILED.value,
            "repair_action": "Inspect the provider response.",
            "repair_route": "/video-production/run-1",
            "retryable": False,
            "affected_ids": [job_id],
            "raw": {"provider_result": {"status": "completed", "assets": []}},
        }

    monkeypatch.setattr(worker, "run_provider_stage_agent", fake_agent)
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

    assert result.status == "blocked"
    assert result.code == ProductionErrorCode.PROVIDER_TASK_FAILED.value
    assert result.retryable is False
    assert result.affected_ids == ["job-1"]
    assert result.data["raw"]["provider_result"]["assets"] == []


@pytest.mark.asyncio
async def test_execute_real_job_keeps_unknown_agent_failure_sync_required(monkeypatch, db):
    async def fake_agent(db_arg, *, run_id, job_id, job_stage, runtime_config, agent_runner=None):
        return {"status": "failed", "message": "agent output was not actionable"}

    monkeypatch.setattr(worker, "run_provider_stage_agent", fake_agent)
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

    assert result.status == "blocked"
    assert result.code == ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED
    assert result.retryable is True
