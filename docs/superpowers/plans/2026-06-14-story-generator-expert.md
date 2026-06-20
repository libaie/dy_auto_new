# Story Generator Expert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real `story_generator` expert and run series story planning through the same durable job/status model as style lock.

**Architecture:** Add a focused story generation runtime service that owns expert source loading, `script_generation` model resolution, JSON contract parsing, and invocation persistence. Keep `generate_series_story_plan()` as the single artifact-writing entry point, then wrap manual API calls in a `ProductionJob` worker while production start keeps a synchronous preflight call to the same service.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Vitest, OpenAI-compatible chat completions.

---

### Task 1: Register Story Generator Expert

**Files:**
- Create: `server/app/data/agency_agents_zh/creative/story-generator.md`
- Modify: `server/app/data/agency_agents_zh/manifest.json`
- Modify: `server/app/services/agency_manifest.py`
- Modify: `server/app/services/video_agency_team.py`
- Modify: `server/app/services/agency_orchestrator.py`
- Modify: `web/src/components/agency/agencyExpertLabels.js`
- Test: `server/tests/test_agency_manifest.py`
- Test: `server/tests/test_agency_orchestrator.py`
- Test: `web/src/__tests__/agency-console-page.test.js`

- [ ] **Step 1: Write failing tests**

Add assertions that `story_generator` appears in manifest verification, team summary, `STAGE_DAG["story_planning"]`, and frontend expert/stage labels.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\codex\dy_auto_new\server
python -m pytest tests/test_agency_manifest.py tests/test_agency_orchestrator.py -q
cd D:\codex\dy_auto_new\web
npx vitest run src/__tests__/agency-console-page.test.js
```

Expected: failures mention missing `story_generator` or `story_planning`.

- [ ] **Step 3: Implement expert registration**

Add the markdown source, update the manifest hash and expected ID tuple, add the core role and phase mapping, add `story_planning` DAG with `lead="story_generator"`, and add frontend labels.

- [ ] **Step 4: Run tests to verify pass**

Run the same commands. Expected: the new expert and stage tests pass.

### Task 2: Add Story Generator Runtime

**Files:**
- Create: `server/app/services/story_generator_expert.py`
- Modify: `server/app/services/series_planning_service.py`
- Test: `server/tests/test_series_planning_service.py`

- [ ] **Step 1: Write failing tests**

Add tests that `generate_series_story_plan()` calls a story expert runtime, writes `expert_id="story_generator"` trace metadata, creates/finalizes an `AgencyExpertInvocation`, and does not produce repair tasks or creative patches on success.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\codex\dy_auto_new\server
python -m pytest tests/test_series_planning_service.py -q
```

Expected: failures mention missing story expert runtime or old `ai_generator.generate_custom` path.

- [ ] **Step 3: Implement minimal runtime**

Create `generate_story_plan_with_expert()` with a strict JSON schema, OpenAI-compatible request support, robust parsing, redacted trace metadata, and safe invocation summary. Change `generate_series_story_plan()` to call this runtime and retain deterministic fallback.

- [ ] **Step 4: Run tests to verify pass**

Run the same pytest command. Expected: planning tests pass.

### Task 3: Durable Story Planning Job

**Files:**
- Modify: `server/app/routers/series.py`
- Modify: `server/app/main.py`
- Test: `server/tests/test_series_api.py`
- Test: `server/tests/test_series_style_lock_pipeline.py`
- Test: `server/tests/test_style_lock_background_worker.py`

- [ ] **Step 1: Write failing tests**

Add tests for queued response from `POST /api/series/{id}/story-plan`, duplicate `409 STORY_PLANNING_IN_PROGRESS`, worker step completion, and background worker calling `_run_story_plan_worker_step`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\codex\dy_auto_new\server
python -m pytest tests/test_series_api.py tests/test_series_style_lock_pipeline.py tests/test_style_lock_background_worker.py -q
```

Expected: failures mention inline story generation or missing worker step.

- [ ] **Step 3: Implement durable job flow**

Add `STORY_PLANNING_STAGE`, active job lookup, enqueue helper, status setter, `_run_story_plan_job()`, `_run_story_plan_worker_step()`, worker-step endpoint, and app background loop. Keep status in `story_bible_json.story_planning`.

- [ ] **Step 4: Run tests to verify pass**

Run the same pytest command. Expected: story-planning job tests pass.

### Task 4: Production Preflight Contract

**Files:**
- Modify: `server/app/services/production_run_service.py` only if the existing call path needs adjustment.
- Test: `server/tests/test_video_production_start_flow_contract.py`

- [ ] **Step 1: Write failing test**

Assert production start consumes artifacts created by the same `generate_series_story_plan()` path and receives `model_trace.expert_id == "story_generator"` when generation runs.

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd D:\codex\dy_auto_new\server
python -m pytest tests/test_video_production_start_flow_contract.py -q
```

Expected: failure if the preflight bypasses the new expert trace.

- [ ] **Step 3: Implement minimal adjustment**

Keep production preflight synchronous. Do not enqueue a second job. Update only if the current call does not reach the new expert runtime.

- [ ] **Step 4: Run test to verify pass**

Run the same pytest command. Expected: production start contract passes.

### Task 5: Frontend Persisted Status And Polling

**Files:**
- Modify: `web/src/api/series.js`
- Modify: `web/src/views/SeriesDetailPage.vue`
- Test: `web/src/__tests__/api-clients.test.js`
- Test: `web/src/__tests__/series-detail-agency.test.js`

- [ ] **Step 1: Write failing tests**

Add tests that the queued response shape is accepted, persisted active status disables the button, the page polls while active, polling stops at terminal status, and expert traces label artifacts as `故事生成专家`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\codex\dy_auto_new\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-agency.test.js
```

Expected: failures mention local-only `storyPlanning`, no polling, or generic source label.

- [ ] **Step 3: Implement minimal UI behavior**

Read `series.story_bible_json.story_planning`, treat `planning`, `queued`, and `running` as active, start reload polling while active, stop at `completed`, `fallback`, or `failed`, and map `model_trace_json.expert_id == "story_generator"` to `故事生成专家`.

- [ ] **Step 4: Run tests to verify pass**

Run the same Vitest command. Expected: frontend tests pass.

### Task 6: Focused Verification

**Files:**
- No new code files.

- [ ] **Step 1: Run backend focused suite**

```powershell
cd D:\codex\dy_auto_new\server
python -m pytest tests/test_agency_manifest.py tests/test_agency_orchestrator.py tests/test_series_planning_service.py tests/test_series_api.py tests/test_series_style_lock_pipeline.py tests/test_style_lock_background_worker.py tests/test_video_production_start_flow_contract.py -q
```

- [ ] **Step 2: Run frontend focused suite**

```powershell
cd D:\codex\dy_auto_new\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-agency.test.js src/__tests__/agency-console-page.test.js
```

- [ ] **Step 3: Inspect changed files**

```powershell
cd D:\codex\dy_auto_new
git diff -- server/app/services/story_generator_expert.py server/app/services/series_planning_service.py server/app/routers/series.py server/app/main.py web/src/views/SeriesDetailPage.vue
```

Expected: changed lines map directly to the approved story generator expert flow.

## Self-Review

- Spec coverage: all approved requirements map to tasks 1-5.
- Placeholder scan: no `TBD`, `fill in`, or `similar to` placeholders remain.
- Type consistency: service entrypoint is `generate_story_plan_with_expert()`, stage is `story_planning`, expert ID is `story_generator`, model scene is `script_generation`.
