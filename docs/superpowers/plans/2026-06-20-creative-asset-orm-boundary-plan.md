# Creative Asset ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `Character` and `Scene` ORM class bodies out of `app.db_models`.

**Architecture:** Add the two asset models to `app.db.models.creative_library`, keep legacy `app.db_models` re-exports, and switch creative library domain imports to the domain ORM path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest creative library tests.

---

### Task 1: Character And Scene ORM Boundary

**Files:**
- Modify: `server/tests/test_creative_library_orm_boundary.py`
- Modify: `server/app/db/models/creative_library.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/creative_library/README.md`
- Modify creative library modules that import `Character` or `Scene` from `app.db_models`.

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.creative_library` to export `Character` and `Scene`,
and match the legacy `app.db_models` exports.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_orm_boundary.py -q
```

Expected: FAIL with `ImportError` for missing `Character` / `Scene` exports.

- [x] **Step 3: Move the class bodies**

Move `Character` and `Scene` into
`server/app/db/models/creative_library.py`, import them in
`server/app/db_models.py`, and remove the old class bodies.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.creative_library` for `Character` / `Scene` inside
`server/app/domains/creative_library`, and document the boundary.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_orm_boundary.py server/tests/test_creative_library_anchor_orm_boundary.py server/tests/test_creative_library_domain_boundary.py server/tests/test_creative_library_router_facade.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*\b(Character|Scene)\b|from app\.db_models import (Character|Scene)\b" server/app/domains/creative_library -g "*.py"
```

Expected: no creative library imports of `Character` or `Scene` from
`app.db_models`.
