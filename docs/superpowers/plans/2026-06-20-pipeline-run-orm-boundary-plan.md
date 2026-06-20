# Pipeline Run ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the script pipeline run ORM class body out of `app.db_models`.

**Architecture:** Add `PipelineRun` to `app.db.models.script_pipeline`, keep the legacy `app.db_models` re-export, and update the script pipeline owner domain to import the domain model path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest script pipeline boundary tests.

---

### Task 1: Pipeline Run ORM Boundary

**Files:**
- Create: `server/tests/test_pipeline_run_orm_boundary.py`
- Create: `server/app/db/models/script_pipeline.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/db/models/ai_video_series.py`
- Modify: `server/app/domains/script_pipeline/script_pipeline_service.py`
- Modify: `server/app/domains/script_pipeline/pipeline_router.py`
- Modify: `server/app/domains/script_pipeline/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.script_pipeline.PipelineRun` to exist and match the
legacy `app.db_models` export.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pipeline_run_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError` for the missing model module.

- [x] **Step 3: Move the class body**

Create `server/app/db/models/script_pipeline.py`, import `PipelineRun` in
`server/app/db_models.py`, and remove the old class body.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.script_pipeline.PipelineRun` in `script_pipeline_service.py`
and `pipeline_router.py`, and record the boundary in the domain README.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pipeline_run_orm_boundary.py server/tests/test_script_pipeline_domain_boundary.py server/tests/test_ai_video_series_orm_boundary.py server/tests/test_pipeline_saved_storyboard_compat.py -q
```
