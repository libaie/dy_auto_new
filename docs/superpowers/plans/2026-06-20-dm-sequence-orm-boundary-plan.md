# DM Sequence ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the DM sequence ORM class body out of `app.db_models`.

**Architecture:** Add `DMSequence` to `app.db.models.content_collection`, re-export it from `app.db_models`, and update production imports that read or mutate DM sequences.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest content collection and device endpoint tests.

---

### Task 1: DM Sequence ORM Boundary

**Files:**
- Modify: `server/tests/test_content_collection_orm_boundary.py`
- Modify: `server/app/db/models/content_collection.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/content_collection/mutations.py`
- Modify: `server/app/domains/content_collection/dm_sequence_visibility.py`
- Modify: `server/app/domains/task_operations/param_resolution.py`
- Modify: `server/app/domains/account_operations/channel_service.py`
- Modify: `server/app/domains/content_collection/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.content_collection.DMSequence` to exist and match
`app.db_models.DMSequence`.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py -q
```

Expected: FAIL because `DMSequence` is not exported from the domain model
module yet.

- [x] **Step 3: Move the class body**

Add `DMSequence` to `server/app/db/models/content_collection.py`, import it
from `server/app/db_models.py`, and remove the old class body.

- [x] **Step 4: Update production imports and docs**

Use `app.db.models.content_collection.DMSequence` in content collection,
task operation, and account operation modules that query DM sequences.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py server/tests/test_content_collection_mutations.py server/tests/test_dm_sequences_api.py server/tests/test_dm_sequence_visibility_domain_import.py server/tests/test_device_endpoints.py -q
```
