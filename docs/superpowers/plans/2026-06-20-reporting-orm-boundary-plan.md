# Reporting ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move reporting stats ORM class bodies out of `app.db_models`.

**Architecture:** Add `app.db.models.reporting` for `DailyStats` and `StatsEvent`, keep legacy re-exports, and update reporting-owned imports. Device stats increment keeps route ownership in `device_operations` while using the reporting stats model.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest boundary and stats tests.

---

### Task 1: Reporting ORM Boundary

**Files:**
- Create: `server/tests/test_reporting_orm_boundary.py`
- Create: `server/app/db/models/reporting.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/reporting/stats_service.py`
- Modify: `server/app/domains/reporting/stats_router.py`
- Modify: `server/app/domains/device_operations/reporting.py`
- Modify: `server/app/domains/reporting/README.md`
- Modify: `server/tests/test_reporting_domain_boundary.py`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.reporting.DailyStats` and `StatsEvent` to exist and
match the legacy `app.db_models` names.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Move the class bodies**

Create `server/app/db/models/reporting.py`, import both names from it in
`server/app/db_models.py`, and remove the old class bodies.

- [x] **Step 4: Update reporting imports and docs**

Use `app.db.models.reporting` in reporting modules and device stats increment.
Document the ORM facade.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_orm_boundary.py server/tests/test_reporting_domain_boundary.py server/tests/test_reporting_router_facade.py server/tests/test_reporting_stats_service_facade.py server/tests/test_stats_service.py server/tests/test_stats_api.py server/tests/test_device_operations_polling_reporting.py -q
```
