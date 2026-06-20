# Device ORM Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `Device` ORM class body out of `app.db_models`.

**Architecture:** Add `Device` to `app.db.models.device_operations`, keep a legacy `app.db_models.Device` re-export, and update device operations modules to use the domain model path.

**Tech Stack:** SQLAlchemy ORM, shared `app.db.base.Base`, pytest device operations tests.

---

### Task 1: Device ORM Boundary

**Files:**
- Modify: `server/tests/test_device_operations_orm_boundary.py`
- Modify: `server/app/db/models/device_operations.py`
- Modify: `server/app/db_models.py`
- Modify: `server/app/domains/device_operations/admin_router.py`
- Modify: `server/app/domains/device_operations/device_service.py`
- Modify: `server/app/domains/device_operations/pairing.py`
- Modify: `server/app/domains/device_operations/script_assets.py`
- Modify: `server/app/domains/device_operations/status_lifecycle.py`
- Modify: `server/app/domains/device_operations/status_ws.py`
- Modify: `server/app/domains/device_operations/README.md`

- [x] **Step 1: Write the failing boundary test**

Require `app.db.models.device_operations` to export `Device` and match the
legacy `app.db_models.Device` export.

- [x] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_orm_boundary.py -q
```

Expected: FAIL with `ImportError` for the missing `Device` export.

- [x] **Step 3: Move the class body**

Move `Device` into `server/app/db/models/device_operations.py`, import it in
`server/app/db_models.py`, and remove the old class body.

- [x] **Step 4: Update device operations imports and docs**

Use `app.db.models.device_operations` for `Device` and `DevicePairRequest`
inside the device operations domain, and record the boundary in the README.

- [x] **Step 5: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_orm_boundary.py server/tests/test_device_service_domain_facade.py server/tests/test_device_operations_pairing.py server/tests/test_devices_api.py -q
```

Then run:

```powershell
rg -n "from app\.db_models import .*\b(Device|DevicePairRequest)\b|from app\.db_models import (Device|DevicePairRequest)\b" server/app/domains/device_operations -g "*.py"
```

Expected: no device operations imports of `Device` from `app.db_models`.
