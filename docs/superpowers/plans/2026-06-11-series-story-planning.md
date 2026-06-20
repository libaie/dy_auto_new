# Series Story Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real series-level story planning flow that generates a whole-series plan and rich per-episode story cards, then feeds those cards into existing episode script/storyboard production.

**Architecture:** Extend `server/app/services/series_planning_service.py` with async story planning, persist results in `AITextArtifact`, expose `POST /api/series/{series_id}/story-plan`, inject approved story context in `production_run_service.py`, and add a compact control/status in `web/src/views/SeriesDetailPage.vue`.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Vitest, existing AI text artifact ledger, existing script generation model config.

---

## Task 1: Backend Story Planning Service

- [x] Add tests in `server/tests/test_series_planning_service.py`.
  - Verify all episode placeholders exist before planning.
  - Verify `series_story_plan`, `season_arc`, `continuity_ledger`, and one rich `episode_outline` per target episode are approved.
  - Verify idempotent reruns do not create duplicate AI artifacts when good approved planning already exists.
  - Verify `human_edit` approved `episode_outline` is preserved.
  - Verify model failure creates fallback artifacts with `model_trace_json.stage_status == "fallback"`.
- [x] Implement async `generate_series_story_plan(db, series_id, force=False)` in `server/app/services/series_planning_service.py`.
  - Use existing `ai_generator.generate_custom`.
  - Parse JSON using a small local parser.
  - Normalize missing episode cards with deterministic fallback.
  - Use `AITextArtifactService.approve_artifact` for generated artifacts.

Verify:

```powershell
D:\codex\dy_auto_new\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py -q
```

## Task 2: API Endpoint

- [x] Update `server/app/routers/series.py`.
  - Import `generate_series_story_plan`.
  - Add `POST /api/series/{series_id}/story-plan`.
  - Return artifact summaries and changed episode numbers.
- [x] Add API coverage in `server/tests/test_series_api.py`.

Verify:

```powershell
D:\codex\dy_auto_new\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py -q
```

## Task 3: Production Context Integration

- [x] Update `server/app/services/ai_text_artifact_service.py`.
  - Include `series_story_plan` and `season_arc` in series run artifact consumption order.
- [x] Update `server/app/services/production_run_service.py`.
  - Ensure story planning artifacts exist before script generation when missing.
  - Inject approved `series_story_plan`, `season_arc`, `continuity_ledger`, and `episode_outline` into `_script_generation_source_prompt`.
  - Keep prompt size bounded by summarizing JSON.
- [x] Update production start contract tests.

Verify:

```powershell
D:\codex\dy_auto_new\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py server/tests/test_script_pipeline.py -q
```

## Task 4: Frontend Control and Display

- [x] Update `web/src/api/series.js`.
  - Add `generateSeriesStoryPlan(seriesId)`.
- [x] Update `web/src/views/SeriesDetailPage.vue`.
  - Add "生成整季故事规划" button with loading/error state.
  - Refresh artifacts after generation.
  - Display richer episode outline content in existing expanded episode panel.
- [x] Update `web/src/__tests__/api-clients.test.js` and `web/src/__tests__/series-detail-agency.test.js`.

Verify:

```powershell
cd D:\codex\dy_auto_new\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-agency.test.js
```

## Task 5: Final Verification

- [x] Run focused backend tests:

```powershell
D:\codex\dy_auto_new\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py server/tests/test_series_api.py server/tests/test_video_production_start_flow_contract.py server/tests/test_script_pipeline.py -q
```

- [x] Run focused frontend tests:

```powershell
cd D:\codex\dy_auto_new\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-agency.test.js
```

- [x] Compile touched Python modules:

```powershell
D:\codex\dy_auto_new\server\.venv\Scripts\python.exe -m compileall server/app/services/series_planning_service.py server/app/routers/series.py server/app/services/production_run_service.py server/app/services/ai_text_artifact_service.py
```

## Execution Notes

- Do not create new DB tables.
- Do not overwrite human-approved story outlines.
- Do not generate full second-by-second storyboards for all episodes up front.
- Keep existing style lock semantics untouched.
