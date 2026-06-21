# AI Video LangChain Provider Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the AI video AI application layer with LangChain LLM + tools so agents orchestrate text generation, image generation, video generation, provider submit/query, and multi-agent review.

**Architecture:** Keep the already-created LangChain model adapter, JSON runner, and base tools. Add guarded provider tools that let agents submit/query image and video provider jobs while reusing existing budget, idempotency, provider client, persistence, status, and audit services. Route agency review, story/script/style/storyboard generation, and provider stages through LangChain agents without changing public route contracts.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic v2, LangChain `1.3.10`, `langchain-openai` `1.3.2`, pytest.

---

## Scope Check

This plan supersedes `docs/superpowers/plans/2026-06-21-ai-video-langchain-agent-orchestration.md` after commit `52e9629`. The completed foundation remains valid:

- `server/app/domains/ai_video_series/langchain_runtime/models.py`
- `server/app/domains/ai_video_series/langchain_runtime/agent_runner.py`
- `server/app/domains/ai_video_series/langchain_runtime/tools.py`
- `server/tests/test_ai_video_langchain_models.py`
- `server/tests/test_ai_video_langchain_agent_runner.py`
- `server/tests/test_ai_video_langchain_tools.py`

Do not reimplement those files except where a task below explicitly modifies them.

## File Structure

- Create `server/app/domains/ai_video_series/langchain_runtime/provider_tools.py`: LangChain tools for guarded image/video submit/query/compose provider operations.
- Create `server/app/domains/ai_video_series/langchain_runtime/provider_stage_orchestrator.py`: agent wrapper that lets a stage agent call provider tools for one production job.
- Modify `server/app/domains/ai_video_series/langchain_runtime/tools.py`: expose provider tools through the existing tool registry without import-time DB/config side effects.
- Modify `server/app/domains/video_production/production_worker_service.py`: route real provider job execution through the provider-stage agent orchestrator.
- Modify `server/app/domains/agency_operations/agency_runtime.py`: use `LangChainAgentRunner` for expert output.
- Modify `server/app/domains/ai_video_series/story_generator_expert.py`: use `LangChainAgentRunner` when no injected `model_client` is supplied.
- Modify `server/app/domains/script_pipeline/script_pipeline_service.py`: use `LangChainAgentRunner` for default script model calls.
- Modify `server/app/domains/director_planning/director_router.py`: use structured LangChain JSON for auto storyboard generation.
- Modify `server/app/domains/ai_video_series/style_lock.py`: use structured LangChain JSON for character and scene extraction.
- Modify `server/app/domains/script_pipeline/pipeline_router.py`: replace route-local Pixelle submit/poll helpers with provider tools or existing provider services behind provider tools.
- Create or modify tests under `server/tests/` for each task.
- Create `server/tests/test_ai_video_langchain_inventory.py`: final guard against legacy AI video AI/provider entry points.

---

### Task 1: Add Guarded Provider Tools

**Files:**
- Create: `server/app/domains/ai_video_series/langchain_runtime/provider_tools.py`
- Modify: `server/app/domains/ai_video_series/langchain_runtime/tools.py`
- Test: `server/tests/test_ai_video_langchain_provider_tools.py`
- Test: `server/tests/test_ai_video_langchain_tools.py`

- [ ] **Step 1: Write failing provider tool tests**

Create `server/tests/test_ai_video_langchain_provider_tools.py`:

```python
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


def test_provider_tools_import_has_no_config_side_effects_under_production_debug():
    import os
    import subprocess
    import sys
    from pathlib import Path

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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_provider_tools.py -q
```

Expected: import failure for `app.domains.ai_video_series.langchain_runtime.provider_tools`.

- [ ] **Step 3: Implement the provider tools**

Create `server/app/domains/ai_video_series/langchain_runtime/provider_tools.py`:

```python
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.domains.agency_operations.agency_runtime_contracts import AgencyRuntimeError


def _load_run_and_job(db: Session, run_id: str, job_id: str):
    from app.db.models.video_production import ProductionJob, VideoProductionRun

    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Video production run not found.")
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job or job.plan_id != run.production_plan_id:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Production job not found for run.")
    return run, job


def _result_payload(result: Any) -> dict[str, Any]:
    data = result.data if isinstance(getattr(result, "data", None), dict) else {}
    provider_result = data.get("provider_result") if isinstance(data.get("provider_result"), dict) else {}
    return {
        "status": str(getattr(result, "status", "")),
        "message": str(getattr(result, "message", "")),
        "provider_stage_task_id": data.get("provider_stage_task_id") or provider_result.get("provider_stage_task_id"),
        "provider_task_id": provider_result.get("provider_task_id") or provider_result.get("stage_task_id") or provider_result.get("task_id"),
        "provider_status": provider_result.get("status"),
        "asset_count": len(provider_result.get("assets") or []),
        "raw": data,
    }


async def _execute_provider_job(db: Session, run: Any, job: Any) -> Any:
    from app.domains.video_production.production_worker_service import execute_real_job

    return await execute_real_job(db, run, job)


async def _run_provider_job(db: Session | None, *, run_id: str, job_id: str, expected_stage: str) -> dict[str, Any]:
    if db is None:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Database session is required.")
    run, job = _load_run_and_job(db, run_id, job_id)
    if job.stage != expected_stage:
        raise ValueError(f"Provider tool expected stage {expected_stage}, got {job.stage}.")
    return _result_payload(await _execute_provider_job(db, run, job))


def build_provider_tools(db: Session | None, allowed_tools: list[str] | None = None) -> list[Any]:
    selected = set([
        "submit_image_generation",
        "query_image_task",
        "submit_video_generation",
        "query_video_task",
        "submit_compose",
        "query_compose_task",
    ] if allowed_tools is None else allowed_tools)

    @tool
    async def submit_image_generation(run_id: str, job_id: str) -> dict[str, Any]:
        """Submit or resume one image_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="image_generation")

    @tool
    async def query_image_task(run_id: str, job_id: str) -> dict[str, Any]:
        """Query or sync one image_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="image_generation")

    @tool
    async def submit_video_generation(run_id: str, job_id: str) -> dict[str, Any]:
        """Submit or resume one video_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="video_generation")

    @tool
    async def query_video_task(run_id: str, job_id: str) -> dict[str, Any]:
        """Query or sync one video_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="video_generation")

    @tool
    async def submit_compose(run_id: str, job_id: str) -> dict[str, Any]:
        """Submit or resume one compose production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="compose")

    @tool
    async def query_compose_task(run_id: str, job_id: str) -> dict[str, Any]:
        """Query or sync one compose production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="compose")

    tools_by_name = {
        "submit_image_generation": submit_image_generation,
        "query_image_task": query_image_task,
        "submit_video_generation": submit_video_generation,
        "query_video_task": query_video_task,
        "submit_compose": submit_compose,
        "query_compose_task": query_compose_task,
    }
    return [tools_by_name[name] for name in tools_by_name if name in selected]
```

- [ ] **Step 4: Expose provider tools through `build_ai_video_tools`**

In `server/app/domains/ai_video_series/langchain_runtime/tools.py`, update `build_ai_video_tools` after `tools_by_name` is defined:

```python
    if allowed_tools is None:
        from app.domains.ai_video_series.langchain_runtime.provider_tools import build_provider_tools

        return [*tools_by_name.values(), *build_provider_tools(db)]
    local_tools = [tools_by_name[name] for name in tools_by_name if name in selected]
    provider_names = [
        "submit_image_generation",
        "query_image_task",
        "submit_video_generation",
        "query_video_task",
        "submit_compose",
        "query_compose_task",
    ]
    requested_provider_tools = [name for name in provider_names if name in selected]
    if not requested_provider_tools:
        return local_tools
    from app.domains.ai_video_series.langchain_runtime.provider_tools import build_provider_tools

    return [*local_tools, *build_provider_tools(db, allowed_tools=requested_provider_tools)]
```

- [ ] **Step 5: Add registry tests**

Append to `server/tests/test_ai_video_langchain_tools.py`:

```python
def test_build_ai_video_tools_can_select_provider_tool(db):
    tools = build_ai_video_tools(db=None, allowed_tools=["submit_image_generation"])

    assert [tool.name for tool in tools] == ["submit_image_generation"]
    assert tools[0].coroutine is not None
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_tools.py server/tests/test_ai_video_langchain_provider_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add server/app/domains/ai_video_series/langchain_runtime/tools.py server/app/domains/ai_video_series/langchain_runtime/provider_tools.py server/tests/test_ai_video_langchain_tools.py server/tests/test_ai_video_langchain_provider_tools.py
git commit -m "feat: add ai video langchain provider tools"
```

---

### Task 2: Add Provider Stage Agent Orchestrator

**Files:**
- Create: `server/app/domains/ai_video_series/langchain_runtime/provider_stage_orchestrator.py`
- Test: `server/tests/test_ai_video_langchain_provider_stage_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator tests**

Create `server/tests/test_ai_video_langchain_provider_stage_orchestrator.py`:

```python
import pytest

from app.domains.ai_video_series.langchain_runtime.provider_stage_orchestrator import run_provider_stage_agent


class FakeRunner:
    def __init__(self):
        self.calls = []

    async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
        self.calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "runtime_config": runtime_config,
            "tool_names": [tool.name for tool in tools],
        })
        return {
            "status": "success",
            "message": "agent submitted image",
            "provider_stage_task_id": "pst-1",
            "asset_count": 1,
        }


@pytest.mark.asyncio
async def test_provider_stage_agent_restricts_tools_by_job_stage(db):
    runner = FakeRunner()

    result = await run_provider_stage_agent(
        db,
        run_id="run-1",
        job_id="job-1",
        job_stage="image_generation",
        runtime_config={"provider": "mock", "model": "orchestrator"},
        agent_runner=runner,
    )

    assert result["status"] == "success"
    assert runner.calls[0]["tool_names"] == ["submit_image_generation", "query_image_task"]
    assert '"job_id": "job-1"' in runner.calls[0]["user_prompt"]
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_provider_stage_orchestrator.py -q
```

Expected: import failure for `provider_stage_orchestrator`.

- [ ] **Step 3: Implement the orchestrator**

Create `server/app/domains/ai_video_series/langchain_runtime/provider_stage_orchestrator.py`:

```python
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.domains.ai_video_series.langchain_runtime.agent_runner import LangChainAgentRunner
from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools


STAGE_TOOLS = {
    "image_generation": ["submit_image_generation", "query_image_task"],
    "video_generation": ["submit_video_generation", "query_video_task"],
    "compose": ["submit_compose", "query_compose_task"],
}


async def run_provider_stage_agent(
    db: Session,
    *,
    run_id: str,
    job_id: str,
    job_stage: str,
    runtime_config: dict[str, Any],
    agent_runner: LangChainAgentRunner | None = None,
) -> dict[str, Any]:
    allowed_tools = STAGE_TOOLS.get(job_stage)
    if not allowed_tools:
        raise ValueError(f"Unsupported provider agent stage: {job_stage}")
    runner = agent_runner or LangChainAgentRunner()
    return await runner.run_json(
        system_prompt=(
            "You are an AI video provider stage operator. "
            "Use only the provided tools to submit/query provider work. "
            "Return a JSON object with status, message, provider_stage_task_id, provider_task_id, and asset_count."
        ),
        user_prompt=json.dumps(
            {
                "run_id": run_id,
                "job_id": job_id,
                "job_stage": job_stage,
                "required_sequence": allowed_tools,
            },
            ensure_ascii=False,
        ),
        runtime_config=runtime_config,
        tools=build_ai_video_tools(db, allowed_tools=allowed_tools),
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_provider_stage_orchestrator.py server/tests/test_ai_video_langchain_provider_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/domains/ai_video_series/langchain_runtime/provider_stage_orchestrator.py server/tests/test_ai_video_langchain_provider_stage_orchestrator.py
git commit -m "feat: add ai video provider stage agent orchestrator"
```

---

### Task 3: Route Real Provider Worker Jobs Through Agents

**Files:**
- Modify: `server/app/domains/video_production/production_worker_service.py`
- Test: `server/tests/test_ai_video_langchain_provider_worker.py`

- [ ] **Step 1: Write a failing worker-routing test**

Create `server/tests/test_ai_video_langchain_provider_worker.py`:

```python
import pytest

from app.domains.video_production import production_worker_service as worker


@pytest.mark.asyncio
async def test_execute_real_job_uses_provider_stage_agent(monkeypatch, db):
    calls = []

    async def fake_agent(db_arg, *, run_id, job_id, job_stage, runtime_config, agent_runner=None):
        calls.append((db_arg, run_id, job_id, job_stage, runtime_config["provider"]))
        return {"status": "success", "message": "done", "asset_count": 1}

    monkeypatch.setattr(worker, "run_provider_stage_agent", fake_agent, raising=False)
    monkeypatch.setattr(worker, "_job_spec", lambda db_arg, run, job: {"scene_key": "image_generation", "payload": {}})
    monkeypatch.setattr(
        worker,
        "resolve_runtime_model_config",
        lambda db_arg, scene_key: {"provider": "mock", "model": scene_key},
    )
    run = type("Run", (), {"id": "run-1", "episode_id": "episode-1", "production_plan_id": "plan-1"})()
    job = type("Job", (), {"id": "job-1", "stage": "image_generation", "target_type": "frame", "target_id": "frame-1"})()

    result = await worker.execute_real_job(db, run, job)

    assert result.status == "success"
    assert calls[0][1:4] == ("run-1", "job-1", "image_generation")
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_provider_worker.py -q
```

Expected: failure because `execute_real_job` still calls `ProviderStageExecutor` directly.

- [ ] **Step 3: Route provider stages through `run_provider_stage_agent`**

In `server/app/domains/video_production/production_worker_service.py`, import:

```python
from app.domains.ai_video_series.langchain_runtime.provider_stage_orchestrator import run_provider_stage_agent
```

In `execute_real_job`, replace the `ProviderStageExecutor(...).execute(...)` block with:

```python
    parsed = await run_provider_stage_agent(
        db,
        run_id=run.id,
        job_id=job.id,
        job_stage=job.stage,
        runtime_config=resolve_runtime_model_config(db, "llm_agency_expert_review"),
    )
    if parsed.get("status") != "success":
        return ProductionActionResult.blocked(
            ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED,
            str(parsed.get("message") or "Provider agent did not complete the stage."),
            "Run provider task sync after the provider finishes the task.",
            repair_route=f"/video-production/{run.id}",
            affected_ids=[job.id],
            retryable=True,
            data=parsed,
        )
    return ProductionActionResult.success(
        str(parsed.get("message") or "Provider agent completed the stage."),
        data=parsed,
    )
```

Keep `ProviderStageExecutor`, `PixelleStageClientAdapter`, and `_persist_completed_provider_result` available because provider tools still delegate to `execute_real_job` in Task 1 until this task introduces the agent loop. To avoid recursion, move the current direct provider body into a new helper:

```python
async def execute_provider_job_direct(db: Session, run: VideoProductionRun, job: ProductionJob) -> ProductionActionResult:
    # move the old ProviderStageExecutor implementation here unchanged
```

Then update `provider_tools.py` to import and call `execute_provider_job_direct` instead of `execute_real_job`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_provider_worker.py server/tests/test_ai_video_langchain_provider_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/domains/video_production/production_worker_service.py server/app/domains/ai_video_series/langchain_runtime/provider_tools.py server/tests/test_ai_video_langchain_provider_worker.py server/tests/test_ai_video_langchain_provider_tools.py
git commit -m "feat: route provider worker jobs through langchain agents"
```

---

### Task 4: Replace Agency Expert Runtime With LangChain Runner

**Files:**
- Modify: `server/app/domains/agency_operations/agency_runtime.py`
- Modify: `server/tests/test_agency_runtime.py`

- [ ] **Step 1: Add failing test for runner injection**

Append to `server/tests/test_agency_runtime.py`:

```python
@pytest.mark.asyncio
async def test_runtime_uses_langchain_runner_for_expert_output():
    captured = {}

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            captured["runtime_config"] = runtime_config
            captured["tools"] = [tool.name for tool in tools]
            return {
                "decision": "pass",
                "findings": ["from langchain"],
                "recommendations": [],
                "required_changes": [],
                "evidence": [{"message": "checked"}],
                "status": "passed",
                "token_usage": {"total_tokens": 42},
            }

    runtime = AgencySkillRuntime(agent_runner=FakeRunner())
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={"frame_count": 1},
        runtime_config=_runtime_config(),
    )

    assert result.result_status == "passed"
    assert result.output_summary["findings"] == ["from langchain"]
    assert result.token_usage == {"total_tokens": 42}
    assert captured["runtime_config"]["model"] == "mock-model"
    assert "validate_json" in captured["tools"]
```

- [ ] **Step 2: Remove direct HTTP default-client tests**

Delete these tests from `server/tests/test_agency_runtime.py`:

```text
test_default_client_sends_openai_compatible_request_payload_headers_and_url
test_default_client_sends_multimodal_content_parts
test_default_client_sends_video_content_parts
test_default_client_accepts_openai_chat_completions_protocol
test_default_client_accepts_bailian_chat_completion_provider
test_default_client_rejects_unsupported_provider_before_http_call
test_default_client_maps_rate_limit_and_http_error_to_named_errors
test_default_client_wraps_non_json_provider_response
test_default_client_wraps_missing_choices_body_shape
```

- [ ] **Step 3: Run the new test and verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_runtime.py::test_runtime_uses_langchain_runner_for_expert_output -q
```

Expected: `AgencySkillRuntime.__init__()` does not accept `agent_runner`.

- [ ] **Step 4: Implement LangChain-backed runtime default**

In `server/app/domains/agency_operations/agency_runtime.py`, remove the hand-written `httpx.AsyncClient` default model client and add:

```python
from app.domains.ai_video_series.langchain_runtime.agent_runner import LangChainAgentRunner
from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools
```

Update `AgencySkillRuntime.__init__`:

```python
    def __init__(self, model_client: ModelClient | None = None, agent_runner: Any | None = None):
        self.agent_runner = agent_runner or LangChainAgentRunner()
        if model_client is not None:
            self.model_client = model_client
        else:
            async def default_client(system_prompt: str, user_prompt: MessageContent, config: dict[str, Any]) -> ModelClientResponse:
                parsed = await self.agent_runner.run_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    runtime_config=config,
                    tools=build_ai_video_tools(None, allowed_tools=["validate_json"]),
                )
                return {
                    "content": json.dumps(parsed, ensure_ascii=False),
                    "token_usage": parsed.get("token_usage") if isinstance(parsed.get("token_usage"), dict) else {},
                }

            self.model_client = default_client
```

Keep `httpx` exception mapping in `invoke()` for injected `model_client` tests that raise `httpx.TimeoutException`, `httpx.HTTPStatusError`, or `httpx.RequestError`.

- [ ] **Step 5: Run focused tests and guard search**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_runtime.py -q
rg "httpx.AsyncClient\\(|chat/completions|http_transport" server/app/domains/agency_operations/agency_runtime.py server/tests/test_agency_runtime.py
```

Expected: tests pass; the search prints no direct default client matches.

- [ ] **Step 6: Commit**

```powershell
git add server/app/domains/agency_operations/agency_runtime.py server/tests/test_agency_runtime.py
git commit -m "feat: run agency experts through langchain"
```

---

### Task 5: Replace Story, Script, Director, And Style-Lock LLM Defaults

**Files:**
- Modify: `server/app/domains/ai_video_series/story_generator_expert.py`
- Modify: `server/app/domains/script_pipeline/script_pipeline_service.py`
- Modify: `server/app/domains/director_planning/director_router.py`
- Modify: `server/app/domains/ai_video_series/style_lock.py`
- Test: `server/tests/test_series_planning_service.py`
- Test: `server/tests/test_script_pipeline.py`
- Test: `server/tests/test_director_episode_plan.py`
- Test: `server/tests/test_series_style_lock_pipeline.py`
- Test: `server/tests/test_series_auto_generate_assets.py`

- [ ] **Step 1: Add failing story generator runner-injection test**

Append to `server/tests/test_series_planning_service.py`:

```python
@pytest.mark.asyncio
async def test_story_generator_uses_langchain_runner_when_no_model_client(db):
    from app.domains.ai_video_series.story_generator_expert import generate_story_plan_with_expert

    captured = {}
    payload = _planning_payload(total_episodes=1)

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            captured["tools"] = [tool.name for tool in tools]
            captured["runtime_config"] = runtime_config
            return payload

    series = Series(title="LangChain Story", logline="A secret returns.", total_episodes=1, status="draft")
    character, scene = _add_series_assets(series)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending")
    db.add(episode)
    db.commit()
    payload["episode_outlines"][0]["character_ids"] = [character.id]
    payload["episode_outlines"][0]["scene_ids"] = [scene.id]

    result = await generate_story_plan_with_expert(
        db,
        series=series,
        episodes=[episode],
        character_ids=[character.id],
        scene_ids=[scene.id],
        existing_artifacts=[],
        runtime_config=_runtime_config(),
        agent_runner=FakeRunner(),
    )

    assert result.parsed == payload
    assert "validate_json" in captured["tools"]
    assert "read_series_context" in captured["tools"]
```

- [ ] **Step 2: Add failing script default client test**

Append to `server/tests/test_script_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_default_script_model_client_uses_langchain_runner(monkeypatch):
    calls = []

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            calls.append([tool.name for tool in tools])
            return {"beats": []}

    monkeypatch.setattr(script_pipeline_module, "LangChainAgentRunner", lambda: FakeRunner())

    result = await script_pipeline_module.default_script_model_client(
        system_prompt="system",
        user_prompt="user",
        runtime_config={"provider": "openai-compatible", "model": "m"},
    )

    assert result == {"beats": []}
    assert calls == [["validate_json"]]
```

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py::test_story_generator_uses_langchain_runner_when_no_model_client server/tests/test_script_pipeline.py::test_default_script_model_client_uses_langchain_runner -q
```

Expected: failures because `agent_runner` and `LangChainAgentRunner` are not wired.

- [ ] **Step 4: Replace default story and script model paths**

In `story_generator_expert.py`, add `agent_runner: LangChainAgentRunner | None = None` to `generate_story_plan_with_expert`. When `model_client is None`, call:

```python
parsed = await (agent_runner or LangChainAgentRunner()).run_json(
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    runtime_config=runtime_config,
    tools=build_ai_video_tools(db, allowed_tools=["validate_json", "read_series_context"]),
)
token_usage = parsed.get("token_usage") if isinstance(parsed.get("token_usage"), dict) else {}
raw_output = json.dumps(parsed, ensure_ascii=False)
```

In `script_pipeline_service.py`, make `default_script_model_client`:

```python
async def default_script_model_client(*, system_prompt: str, user_prompt: str, runtime_config: dict[str, Any]) -> Any:
    return await LangChainAgentRunner().run_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        runtime_config=runtime_config,
        tools=build_ai_video_tools(None, allowed_tools=["validate_json"]),
    )
```

- [ ] **Step 5: Replace director and style-lock generation calls**

In `agent_runner.py`, add:

```python
async def run_structured_ai_video_json(
    *,
    system_prompt: str,
    user_prompt: Any,
    runtime_config: dict[str, Any],
    db: Any = None,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools

    return await LangChainAgentRunner().run_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        runtime_config=runtime_config,
        tools=build_ai_video_tools(db, allowed_tools=allowed_tools or ["validate_json"]),
    )
```

Replace AI-video uses of `ai_generator.generate_custom()` in `director_router.py` and `style_lock.py` with `run_structured_ai_video_json(...)`.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py server/tests/test_script_pipeline.py server/tests/test_director_episode_plan.py server/tests/test_series_style_lock_pipeline.py server/tests/test_series_auto_generate_assets.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add server/app/domains/ai_video_series/story_generator_expert.py server/app/domains/script_pipeline/script_pipeline_service.py server/app/domains/director_planning/director_router.py server/app/domains/ai_video_series/style_lock.py server/app/domains/ai_video_series/langchain_runtime/agent_runner.py server/tests/test_series_planning_service.py server/tests/test_script_pipeline.py
git commit -m "feat: run ai video generation prompts through langchain"
```

---

### Task 6: Replace Route-Local Pixelle Submit/Poll Helpers

**Files:**
- Modify: `server/app/domains/script_pipeline/pipeline_router.py`
- Test: existing script pipeline router tests or new `server/tests/test_script_pipeline_provider_tools.py`

- [ ] **Step 1: Write failing route-local provider guard test**

Create `server/tests/test_script_pipeline_provider_tools.py`:

```python
from pathlib import Path


def test_script_pipeline_router_no_longer_calls_pixelle_submit_poll_directly():
    text = Path("server/app/domains/script_pipeline/pipeline_router.py").read_text(encoding="utf-8")

    assert '"/api/video/generate/async"' not in text
    assert '"/api/video/task/' not in text
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline_provider_tools.py -q
```

Expected: failure because `pipeline_router.py` still contains route-local Pixelle submit/poll endpoints.

- [ ] **Step 3: Replace route-local submit/poll**

In `server/app/domains/script_pipeline/pipeline_router.py`, replace `_submit_and_poll(payload, db)` with a call to the provider-stage tool path. Use production jobs when a `run_id` exists; otherwise return a clear `HTTPException(409, "Script pipeline provider rendering requires a production run job.")` instead of directly polling Pixelle.

```python
from app.domains.ai_video_series.langchain_runtime.provider_tools import build_provider_tools
```

For the rendering path that has `run_id` and `job_id`, call:

```python
tools = build_provider_tools(db, allowed_tools=["submit_video_generation", "query_video_task"])
submit_tool = next(tool for tool in tools if tool.name == "submit_video_generation")
result = await submit_tool.ainvoke({"run_id": str(run.id), "job_id": str(job.id)})
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline_provider_tools.py server/tests/test_script_pipeline.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/domains/script_pipeline/pipeline_router.py server/tests/test_script_pipeline_provider_tools.py
git commit -m "feat: route script pipeline provider calls through langchain tools"
```

---

### Task 7: Add AI Video LangChain Inventory Guard And Final Verification

**Files:**
- Create: `server/tests/test_ai_video_langchain_inventory.py`

- [ ] **Step 1: Write inventory guard**

Create `server/tests/test_ai_video_langchain_inventory.py`:

```python
from pathlib import Path


AI_VIDEO_PATHS = [
    Path("server/app/domains/ai_video_series"),
    Path("server/app/domains/director_planning"),
    Path("server/app/domains/script_pipeline"),
    Path("server/app/domains/agency_operations"),
    Path("server/app/domains/video_production"),
]
ALLOW_PROVIDER_MODULES = {
    Path("server/app/domains/ai_video_series/langchain_runtime/provider_tools.py"),
    Path("server/app/domains/video_production/provider_stage_executor.py"),
    Path("server/app/domains/video_production/production_worker_service.py"),
}
FORBIDDEN_PATTERNS = [
    ("ai_generator.generate_custom(", "legacy ai_generator call"),
    ("httpx.AsyncClient(", "direct httpx LLM/provider client"),
    ("chat/completions", "direct chat completions URL"),
    ('"/api/video/generate/async"', "route-local Pixelle video submit"),
    ('"/api/video/task/', "route-local Pixelle video query"),
]


def _python_files(root: Path):
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def test_ai_video_modules_use_langchain_for_ai_and_provider_orchestration():
    offenders = []
    for root in AI_VIDEO_PATHS:
        for path in _python_files(root):
            if path in ALLOW_PROVIDER_MODULES:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern, label in FORBIDDEN_PATTERNS:
                if pattern in text:
                    offenders.append(f"{path}: {label}")

    assert offenders == []
```

- [ ] **Step 2: Run LangChain foundation and inventory tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_inventory.py server/tests/test_ai_video_langchain_models.py server/tests/test_ai_video_langchain_agent_runner.py server/tests/test_ai_video_langchain_tools.py server/tests/test_ai_video_langchain_provider_tools.py server/tests/test_ai_video_langchain_provider_stage_orchestrator.py server/tests/test_ai_video_langchain_provider_worker.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run AI video regression suite**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_runtime.py server/tests/test_agency_orchestrator.py server/tests/test_series_planning_service.py server/tests/test_script_pipeline.py server/tests/test_director_episode_plan.py server/tests/test_series_style_lock_pipeline.py server/tests/test_series_auto_generate_assets.py server/tests/test_video_production_start_flow_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Run app smoke**

Run:

```powershell
$env:PYTHONPATH='server'; .\server\.venv\Scripts\python.exe -c "import app.main; print('routes', len(app.main.app.routes)); import app.db.models as models; print('tables', len(models.Base.metadata.tables))"
```

Expected output includes `routes` and `tables` counts without import errors.

- [ ] **Step 5: Commit final guard**

```powershell
git add server/tests/test_ai_video_langchain_inventory.py
git commit -m "test: guard ai video langchain provider migration"
```

---

## Self-Review

- Spec coverage: Tasks 1-3 implement provider submit/query tools and agent orchestration for image/video/compose stages. Task 4 replaces agency review. Task 5 replaces story, script, director, and style-lock LLM defaults. Task 6 removes route-local provider submit/poll. Task 7 proves the inventory boundary and runs the AI video regression suites.
- Placeholder scan: no placeholder markers or undefined future steps remain.
- Type consistency: provider tools return JSON dictionaries; provider-stage orchestrator consumes those dictionaries; worker integration maps them back to `ProductionActionResult`.
- Scope fit: the plan keeps provider clients intact and moves orchestration to LangChain tools/agents, matching the approved B-1 design.
