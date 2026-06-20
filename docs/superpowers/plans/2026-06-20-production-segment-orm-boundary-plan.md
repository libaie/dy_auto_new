# Production Segment ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `ProductionSegment` ORM definition out of `app.db_models`.

**Architecture:** Define `ProductionSegment` in `app.db.models.video_production`, keep `app.db_models` as a compatibility re-export, and switch video production owner imports to the domain ORM path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest video production tests.

---

### Task 1: ProductionSegment ORM Boundary

**Files:**
- Modify: `server/tests/test_video_production_orm_boundary.py`
- Modify: `server/app/db/models/video_production.py`
- Modify: `server/app/db_models.py`
- Modify: selected `server/app/domains/video_production/*.py` imports

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.video_production` to export `ProductionSegment`,
require the legacy `app.db_models.ProductionSegment` export to be the same
class, and require `ProductionSegment.__module__ ==
"app.db.models.video_production"`.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py -q
```

Expected: FAIL because `ProductionSegment` is still defined in
`app.db_models`.

- [x] **Step 3: Move the class definition**

Move the exact `ProductionSegment` SQLAlchemy class body into
`server/app/db/models/video_production.py`. Import it from that module in
`server/app/db_models.py`.

- [x] **Step 4: Update owner-domain imports**

Use `app.db.models.video_production` for `ProductionSegment` inside
`server/app/domains/video_production`, leaving other unmoved ORM names on
`app.db_models`.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py server/tests/test_video_production_plan_service_facade.py server/tests/test_production_plan_service.py server/tests/test_video_production_tree_api.py server/tests/test_video_production_retry_impact.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*ProductionSegment|from app\.db_models import ProductionSegment\b" server/app/domains/video_production -g "*.py"
```

Expected: no video production owner-domain imports of `ProductionSegment` from
`app.db_models`.
