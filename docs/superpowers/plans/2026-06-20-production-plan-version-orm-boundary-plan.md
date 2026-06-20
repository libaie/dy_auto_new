# Production Plan Version ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `ProductionPlanVersion` ORM definition out of `app.db_models`.

**Architecture:** Define `ProductionPlanVersion` in `app.db.models.video_production`, keep `app.db_models` as a compatibility re-export, and switch video production owner imports to the domain ORM path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest video production tests.

---

### Task 1: ProductionPlanVersion ORM Boundary

**Files:**
- Modify: `server/tests/test_video_production_orm_boundary.py`
- Modify: `server/app/db/models/video_production.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/video_production/production_plan_service.py`
- Modify: `server/app/domains/video_production/mock_scale_scheduler_service.py`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.video_production` to export `ProductionPlanVersion`,
require the legacy `app.db_models.ProductionPlanVersion` export to be the same
class, and require `ProductionPlanVersion.__module__ ==
"app.db.models.video_production"`.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py -q
```

Expected: FAIL because `ProductionPlanVersion` is still defined in
`app.db_models`.

- [x] **Step 3: Move the class definition**

Move the exact `ProductionPlanVersion` SQLAlchemy class body into
`server/app/db/models/video_production.py`. Import it from that module in
`server/app/db_models.py`.

- [x] **Step 4: Update owner-domain imports**

Use `app.db.models.video_production` for `ProductionPlanVersion` inside
`server/app/domains/video_production/production_plan_service.py` and
`server/app/domains/video_production/mock_scale_scheduler_service.py`.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py server/tests/test_video_production_plan_service_facade.py server/tests/test_production_plan_service.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*ProductionPlanVersion|from app\.db_models import ProductionPlanVersion\b" server/app/domains/video_production -g "*.py"
```

Expected: no video production owner-domain imports of `ProductionPlanVersion`
from `app.db_models`.
