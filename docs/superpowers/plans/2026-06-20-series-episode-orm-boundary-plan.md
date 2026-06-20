# Series Episode ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the core series and episode ORM definitions out of `app.db_models`.

**Architecture:** Define `Series`, `Episode`, `series_characters`, and `series_scenes` in `app.db.models.ai_video_series`, keep `app.db_models` as a compatibility re-export, and leave still-unmigrated production ORM names on lazy compatibility exports.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest AI video series tests.

---

### Task 1: Series and Episode ORM Boundary

**Files:**
- Modify: `server/tests/test_ai_video_series_orm_boundary.py`
- Modify: `server/app/db/models/ai_video_series.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/ai_video_series/series_planning_service.py`
- Modify: `server/app/domains/ai_video_series/episode_asset_scope_service.py`
- Modify: `server/app/domains/ai_video_series/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `Series.__module__` and `Episode.__module__` to be
`app.db.models.ai_video_series`.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_orm_boundary.py -q
```

Expected: FAIL because `Series` and `Episode` are still defined in
`app.db_models`.

- [x] **Step 3: Move the class and table definitions**

Move `Series`, `Episode`, `series_characters`, and `series_scenes` into
`server/app/db/models/ai_video_series.py`. Import them from that module in
`server/app/db_models.py`.

- [x] **Step 4: Keep compatibility for unmoved names**

Keep `app.db.models.ai_video_series.__all__` stable. Resolve production ORM
names that still live in `app.db_models` with module `__getattr__`, so imports
such as `from app.db.models.ai_video_series import ProductionJob` keep working.

- [x] **Step 5: Update owner-domain imports**

Use `app.db.models.ai_video_series` for `Series` and `Episode` in
`server/app/domains/ai_video_series`.

- [x] **Step 6: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_orm_boundary.py server/tests/test_ai_video_series_planning_service_facade.py server/tests/test_ai_video_series_episode_asset_scope_service_facade.py server/tests/test_series_planning_service.py server/tests/test_episode_asset_scope_service.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*(Series|Episode)|from app\.db_models import (Series|Episode)\b" server/app/domains/ai_video_series -g "*.py"
```

Expected: no owner-domain imports of `Series` or `Episode` from `app.db_models`.
