# User ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the standalone identity-access `User` ORM class body out of `app.db_models`.

**Architecture:** Add `app.db.models.identity_access.User`, re-export it from `app.db_models`, and update identity-access router imports. Keep `Device` in `app.db_models`.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest import-boundary tests.

---

### Task 1: User ORM Boundary

**Files:**
- Create: `server/tests/test_identity_access_orm_boundary.py`
- Create: `server/app/db/models/identity_access.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/identity_access/auth_router.py`
- Modify: `server/app/domains/identity_access/README.md`
- Modify: `docs/superpowers/specs/2026-06-20-identity-access-domain-design.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.identity_access.User` to exist and match
`app.db_models.User`.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_identity_access_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Move the class body**

Create `server/app/db/models/identity_access.py`, import `User` from it in
`server/app/db_models.py`, and remove the old class body.

- [x] **Step 4: Update identity-access imports and docs**

Use `app.db.models.identity_access.User` inside `auth_router.py`. Keep `Device`
on the legacy path.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_identity_access_orm_boundary.py server/tests/test_identity_access_domain_boundary.py server/tests/test_identity_access_router_facade.py server/tests/test_admin_auth.py -q
```
