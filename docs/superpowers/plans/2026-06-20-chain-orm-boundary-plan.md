# Chain ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `ChainTemplate` and `ChainInstance` ORM class bodies out of `app.db_models`.

**Architecture:** Add both chain models to `app.db.models.account_operations`, keep legacy `app.db_models` re-exports, and switch account operations chain imports to the domain ORM path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest account operations tests.

---

### Task 1: Chain ORM Boundary

**Files:**
- Modify: `server/tests/test_account_operations_orm_boundary.py`
- Modify: `server/app/db/models/account_operations.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/account_operations/README.md`
- Modify: `server/app/domains/account_operations/chain_use_cases.py`
- Modify: `server/app/domains/account_operations/chain_service.py`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.account_operations` to export `ChainTemplate` and
`ChainInstance`, and match legacy `app.db_models` exports.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_orm_boundary.py -q
```

Expected: FAIL with `ImportError` for missing chain model exports.

- [x] **Step 3: Move the class bodies**

Move `ChainTemplate` and `ChainInstance` into
`server/app/db/models/account_operations.py`, import them in
`server/app/db_models.py`, and remove the old class bodies.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.account_operations` for chain models inside
`server/app/domains/account_operations`, and document the boundary.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_orm_boundary.py server/tests/test_account_operations_domain_boundary.py server/tests/test_account_operations_read_models.py server/tests/test_account_operations_chain_orchestration.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*\b(ChainTemplate|ChainInstance)\b|from app\.db_models import (ChainTemplate|ChainInstance)\b" server/app/domains/account_operations -g "*.py"
```

Expected: no account operations imports of chain models from `app.db_models`.
