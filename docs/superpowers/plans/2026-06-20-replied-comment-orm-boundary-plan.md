# Replied Comment ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the standalone replied-comment dedupe ORM class body out of `app.db_models`.

**Architecture:** Add `RepliedComment` to `app.db.models.content_collection`, re-export it from `app.db_models`, and update device content bridge imports. Keep larger content collection persistence graphs in the legacy module for later slices.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest boundary and device bridge tests.

---

### Task 1: Replied Comment ORM Boundary

**Files:**
- Modify: `server/tests/test_content_collection_orm_boundary.py`
- Modify: `server/app/db/models/content_collection.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/device_operations/content_bridge.py`
- Modify: `server/app/domains/content_collection/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.content_collection.RepliedComment` to exist and match
`app.db_models.RepliedComment`.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py -q
```

Expected: FAIL because `RepliedComment` is not exported from the domain model
module yet.

- [x] **Step 3: Move the class body**

Add `RepliedComment` to `server/app/db/models/content_collection.py`, import it
from `server/app/db_models.py`, and remove the old class body.

- [x] **Step 4: Update imports and docs**

Use `app.db.models.content_collection.RepliedComment` in
`device_operations/content_bridge.py` and document the ORM facade.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py server/tests/test_content_collection_domain_boundary.py server/tests/test_content_collection_device_bridge.py server/tests/test_device_endpoints.py -q
```
