# Account ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `Account` ORM class body out of `app.db_models`.

**Architecture:** Add `Account` to `app.db.models.account_operations`, keep a legacy `app.db_models.Account` re-export, and switch account operations imports to the domain ORM path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest account operations tests.

---

### Task 1: Account ORM Boundary

**Files:**
- Create: `server/tests/test_account_operations_orm_boundary.py`
- Create: `server/app/db/models/account_operations.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/account_operations/README.md`
- Modify account operations modules that import `Account` from `app.db_models`.

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.account_operations` to export `Account`, and match the
legacy `app.db_models.Account` export.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for the missing
account operations ORM boundary.

- [x] **Step 3: Move the class body**

Move `Account` into `server/app/db/models/account_operations.py`, import it in
`server/app/db_models.py`, and remove the old class body.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.account_operations` for `Account` inside
`server/app/domains/account_operations`, and document the boundary.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_orm_boundary.py server/tests/test_account_operations_domain_boundary.py server/tests/test_account_operations_read_models.py server/tests/test_account_operations_mutations.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*\bAccount\b|from app\.db_models import Account\b" server/app/domains/account_operations -g "*.py"
```

Expected: no account operations imports of `Account` from `app.db_models`.
