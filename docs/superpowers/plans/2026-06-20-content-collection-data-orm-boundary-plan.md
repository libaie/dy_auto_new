# Content Collection Data ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move collected comment, collected user, and conversation ORM class bodies out of `app.db_models`.

**Architecture:** Add the three data models to `app.db.models.content_collection`, keep legacy `app.db_models` re-exports, and switch content collection domain imports to the domain ORM path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest content collection tests.

---

### Task 1: Collection Data ORM Boundary

**Files:**
- Modify: `server/tests/test_content_collection_orm_boundary.py`
- Modify: `server/app/db/models/content_collection.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/content_collection/README.md`
- Modify: `server/app/domains/content_collection/collection_reports.py`
- Modify: `server/app/domains/content_collection/dm_claims.py`
- Modify: `server/app/domains/content_collection/read_models.py`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.content_collection` to export `CollectedComment`,
`CollectedUser`, and `Conversation`, and match legacy `app.db_models` exports.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py -q
```

Expected: FAIL with `ImportError` for the missing collection data model exports.

- [x] **Step 3: Move the class bodies**

Move `CollectedComment`, `CollectedUser`, and `Conversation` into
`server/app/db/models/content_collection.py`, import them in
`server/app/db_models.py`, and remove the old class bodies.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.content_collection` for the three data models inside
`server/app/domains/content_collection`, and document the boundary.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py server/tests/test_content_collection_read_models.py server/tests/test_content_collection_mutations.py server/tests/test_content_collection_domain_boundary.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*\b(CollectedComment|CollectedUser|Conversation)\b|from app\.db_models import (CollectedComment|CollectedUser|Conversation)\b" server/app/domains/content_collection -g "*.py"
```

Expected: no content collection imports of these data models from
`app.db_models`.
