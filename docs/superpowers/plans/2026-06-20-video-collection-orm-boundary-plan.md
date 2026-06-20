# Video Collection ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the video collection ORM class body out of `app.db_models`.

**Architecture:** Add `VideoCollection` to `app.db.models.video_production`, re-export it from `app.db_models`, and update production imports that create or check collection rows.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest video production and lifecycle tests.

---

### Task 1: Video Collection ORM Boundary

**Files:**
- Create: `server/tests/test_video_production_orm_boundary.py`
- Create: `server/app/db/models/video_production.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/video_production/production_collection_service.py`
- Modify: `server/app/domains/creative_library/asset_lifecycle_service.py`
- Modify: `server/app/domains/video_production/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.video_production.VideoCollection` to exist and match
`app.db_models.VideoCollection`.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Move the class body**

Create `server/app/db/models/video_production.py`, import `VideoCollection`
from it in `server/app/db_models.py`, and remove the old class body.

- [x] **Step 4: Update production imports and docs**

Use `app.db.models.video_production.VideoCollection` in production collection
creation and creative-library lifecycle dependency checks.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py server/tests/test_collection_builder.py server/tests/test_asset_lifecycle_service.py server/tests/test_video_production_collection_service_facade.py -q
```
