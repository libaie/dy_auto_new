# Production Audit Event ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the production audit event ORM class body out of `app.db_models`.

**Architecture:** Add `ProductionAuditEvent` to `app.db.models.production_observability`, keep the legacy `app.db_models` re-export, and update the owner domain service to import the domain model path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest production observability tests.

---

### Task 1: Production Audit Event ORM Boundary

**Files:**
- Create: `server/tests/test_production_audit_event_orm_boundary.py`
- Create: `server/app/db/models/production_observability.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/db/models/ai_video_series.py`
- Modify: `server/app/domains/production_observability/production_observability_service.py`
- Modify: `server/app/domains/production_observability/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.production_observability.ProductionAuditEvent` to exist
and match the legacy `app.db_models` export.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_production_audit_event_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError` for the missing model module.

- [x] **Step 3: Move the class body**

Create `server/app/db/models/production_observability.py`, import
`ProductionAuditEvent` in `server/app/db_models.py`, and remove the old class
body.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.production_observability.ProductionAuditEvent` in
`production_observability_service.py`, and record the boundary in the domain
README.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_production_audit_event_orm_boundary.py server/tests/test_production_observability_domain_facade.py server/tests/test_video_production_observability_events.py server/tests/test_ai_video_series_orm_boundary.py -q
```
