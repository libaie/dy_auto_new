# Script Output ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move script pipeline output ORM class bodies out of `app.db_models`.

**Architecture:** Add `EpisodeScript`, `ScriptDramaticBeat`, `ScriptSceneOutline`, and `ScriptVisualShot` to `app.db.models.script_pipeline`, keep legacy re-exports, and update the script pipeline owner service to import the domain model path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest script pipeline tests.

---

### Task 1: Script Output ORM Boundary

**Files:**
- Create: `server/tests/test_script_output_orm_boundary.py`
- Modify: `server/app/db/models/script_pipeline.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/db/models/ai_video_series.py`
- Modify: `server/app/domains/script_pipeline/script_pipeline_service.py`
- Modify: `server/app/domains/script_pipeline/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.script_pipeline` to export the four script output ORM
classes and match the legacy `app.db_models` exports.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_output_orm_boundary.py -q
```

Expected: FAIL with `ImportError` for the missing script output model exports.

- [x] **Step 3: Move the class bodies**

Move the four class bodies into `server/app/db/models/script_pipeline.py`,
import them in `server/app/db_models.py`, and remove the old class bodies.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.script_pipeline` in `script_pipeline_service.py`, and
record the boundary in the domain README.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_output_orm_boundary.py server/tests/test_script_pipeline_domain_boundary.py server/tests/test_ai_video_series_orm_boundary.py server/tests/test_script_pipeline.py::test_script_sqlalchemy_tables_persist_structured_rows -q
```
