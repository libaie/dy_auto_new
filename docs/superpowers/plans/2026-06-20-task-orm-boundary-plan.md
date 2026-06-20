# Task ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `Task` ORM class body out of `app.db_models` and into the task operations database domain.

**Architecture:** Add `Task` to `app.db.models.task_operations`, keep `app.db_models` as a compatibility re-export, and switch task operations owner imports to the domain ORM path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest task operations tests.

---

### Task 1: Task ORM Boundary

**Files:**
- Create: `server/app/db/models/task_operations.py`
- Create: `server/tests/test_task_operations_orm_boundary.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/task_operations/task_service.py`
- Modify: `server/app/domains/task_operations/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.task_operations` to export `Task`, and require that
export to match the legacy `app.db_models.Task` compatibility path.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for the missing
task operations ORM module.

- [x] **Step 3: Move the class body**

Move the exact `Task` SQLAlchemy class body into
`server/app/db/models/task_operations.py`, import it in
`server/app/db_models.py`, and remove the old inline class body.

- [x] **Step 4: Update owner-domain imports and docs**

Use `app.db.models.task_operations` for `Task` inside
`server/app/domains/task_operations`, and update the README so ORM ownership is
allowed only for this separate approved boundary.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_orm_boundary.py server/tests/test_task_service.py server/tests/test_task_service_domain_facade.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*Task|from app\.db_models import Task\b|Task as DBTask" server/app/domains/task_operations -g "*.py"
```

Expected: no task operations imports of `Task` from `app.db_models`.

Note: `server/tests/test_task_operations_domain_boundary.py` currently has an
existing device/task cross-domain assertion that fails because device polling
and reporting already import `app.domains.task_operations.task_service`; this
slice does not change that neighbor-domain dependency.
