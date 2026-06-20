# Generated Video ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the generated-video ORM class body out of `app.db_models`.

**Architecture:** Add `GeneratedVideo` to `app.db.models.video_library`, re-export it from `app.db_models`, and update production imports that read or write generated-video rows.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest video library and pipeline tests.

---

### Task 1: Generated Video ORM Boundary

**Files:**
- Create: `server/tests/test_video_library_orm_boundary.py`
- Create: `server/app/db/models/video_library.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/video_library/videos_router.py`
- Modify: `server/app/domains/ai_video_series/read_models.py`
- Modify: `server/app/domains/script_pipeline/pipeline_router.py`
- Modify: `server/app/domains/agency_operations/agency_console.py`
- Modify: `server/app/domains/video_production/video_production_service.py`
- Modify: `server/app/domains/task_operations/task_service.py`
- Modify: `server/app/domains/video_library/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.video_library.GeneratedVideo` to exist and match
`app.db_models.GeneratedVideo`.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_library_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Move the class body**

Create `server/app/db/models/video_library.py`, import `GeneratedVideo` from it
in `server/app/db_models.py`, and remove the old class body.

- [x] **Step 4: Update production imports and docs**

Use `app.db.models.video_library.GeneratedVideo` in video library, script
pipeline, AI video series read models, agency console, video production, and
task cleanup code.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_library_orm_boundary.py server/tests/test_video_library_domain_boundary.py server/tests/test_video_library_router_facade.py server/tests/test_video_library_api.py server/tests/test_script_pipeline_router_facade.py server/tests/test_ai_video_series_status_read_model.py server/tests/test_video_production_final_gate.py -q
```
