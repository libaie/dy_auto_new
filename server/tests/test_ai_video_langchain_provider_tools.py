import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.domains.ai_video_series.langchain_runtime import provider_tools


class FakeResult:
    def __init__(self, status="success", data=None, message="ok"):
        self.status = status
        self.data = data or {}
        self.message = message


def _tool(tools, name):
    return next(item for item in tools if item.name == name)


@pytest.mark.asyncio
async def test_provider_tool_uses_direct_provider_helper(monkeypatch, db):
    called = []
    run = type("Run", (), {"id": "run-1", "production_plan_id": "plan-1"})()
    job = type("Job", (), {"id": "job-1", "stage": "image_generation", "plan_id": "plan-1"})()

    async def fake_direct(db_arg, run_arg, job_arg):
        called.append((run_arg.id, job_arg.id))
        return type("Result", (), {"status": "success", "message": "direct", "data": {}})()

    async def fail_routed(*args, **kwargs):
        raise AssertionError("provider tools should use execute_provider_job_direct")

    monkeypatch.setattr(provider_tools, "_load_run_and_job", lambda db_arg, run_id, job_id: (run, job))
    monkeypatch.setattr(
        "app.domains.video_production.production_worker_service.execute_provider_job_direct",
        fake_direct,
        raising=False,
    )
    monkeypatch.setattr(
        "app.domains.video_production.production_worker_service.execute_real_job",
        fail_routed,
    )

    tool = provider_tools.build_provider_tools(db, allowed_tools=["submit_image_generation"])[0]
    result = await tool.ainvoke({"run_id": "run-1", "job_id": "job-1"})

    assert result["status"] == "success"
    assert called == [("run-1", "job-1")]


@pytest.mark.asyncio
async def test_submit_image_generation_uses_existing_worker_service(monkeypatch, db):
    calls = []
    run = type("Run", (), {"id": "run-1", "production_plan_id": "plan-1"})()
    job = type("Job", (), {"id": "job-1", "stage": "image_generation", "plan_id": "plan-1"})()

    async def fake_execute_real_job(db_arg, run, job):
        calls.append((db_arg, run.id, job.id, job.stage))
        return FakeResult(
            data={
                "provider_stage_task_id": "pst-1",
                "provider_result": {"status": "submitted", "assets": []},
            }
        )

    monkeypatch.setattr(provider_tools, "_load_run_and_job", lambda db_arg, run_id, job_id: (run, job))
    monkeypatch.setattr(provider_tools, "_execute_provider_job", fake_execute_real_job)

    tools = provider_tools.build_provider_tools(db, allowed_tools=["submit_image_generation"])
    result = await _tool(tools, "submit_image_generation").ainvoke({"run_id": "run-1", "job_id": "job-1"})

    assert calls == [(db, "run-1", "job-1", "image_generation")]
    assert result["status"] == "success"
    assert result["provider_stage_task_id"] == "pst-1"


@pytest.mark.asyncio
async def test_submit_video_generation_rejects_wrong_stage(monkeypatch, db):
    run = type("Run", (), {"id": "run-1", "production_plan_id": "plan-1"})()
    job = type("Job", (), {"id": "image-job", "stage": "image_generation", "plan_id": "plan-1"})()

    async def fail_execute_real_job(db_arg, run, job):
        raise AssertionError("should not submit wrong stage")

    monkeypatch.setattr(provider_tools, "_load_run_and_job", lambda db_arg, run_id, job_id: (run, job))
    monkeypatch.setattr(provider_tools, "_execute_provider_job", fail_execute_real_job)

    tools = provider_tools.build_provider_tools(db, allowed_tools=["submit_video_generation"])

    with pytest.raises(ValueError, match="video_generation"):
        await _tool(tools, "submit_video_generation").ainvoke({"run_id": "run-1", "job_id": "image-job"})


@pytest.mark.asyncio
async def test_submit_compose_accepts_real_compose_job_stages(monkeypatch, db):
    calls = []
    run = type("Run", (), {"id": "run-1", "production_plan_id": "plan-1"})()
    jobs = {
        stage: type("Job", (), {"id": f"job-{stage}", "stage": stage, "plan_id": "plan-1"})()
        for stage in ("episode_compose", "composition")
    }

    async def fake_execute_real_job(db_arg, run, job):
        calls.append((db_arg, run.id, job.id, job.stage))
        return FakeResult(
            data={
                "provider_stage_task_id": f"pst-{job.stage}",
                "provider_result": {"status": "submitted", "assets": []},
            }
        )

    monkeypatch.setattr(provider_tools, "_load_run_and_job", lambda db_arg, run_id, job_id: (run, jobs[job_id[4:]]))
    monkeypatch.setattr(provider_tools, "_execute_provider_job", fake_execute_real_job)

    tools = provider_tools.build_provider_tools(db, allowed_tools=["submit_compose"])
    submit_compose = _tool(tools, "submit_compose")

    for stage in ("episode_compose", "composition"):
        result = await submit_compose.ainvoke({"run_id": "run-1", "job_id": f"job-{stage}"})
        assert result["provider_stage_task_id"] == f"pst-{stage}"

    assert calls == [
        (db, "run-1", "job-episode_compose", "episode_compose"),
        (db, "run-1", "job-composition", "composition"),
    ]


def test_provider_tools_import_has_no_config_side_effects_under_production_debug():
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "server")
    env["DEBUG"] = "false"
    for key in ("DEVICE_SECRET", "ADMIN_PASSWORD", "JWT_SECRET"):
        env.pop(key, None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.domains.ai_video_series.langchain_runtime.provider_tools; print('import-ok')",
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    assert "import-ok" in completed.stdout
