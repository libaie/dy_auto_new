# Video Production Provider Cost Reservation Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move provider cost reservation lifecycle logic into the video
production domain while preserving old service imports and module-level lock
state.

**Architecture:** The implementation lives in
`app.domains.video_production.provider_cost_reservation_service`.
`app.services.provider_cost_reservation_service` becomes a `sys.modules` facade
so old callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create:
  `server/app/domains/video_production/provider_cost_reservation_service.py`
  - Owns `_ACTIVE_RESERVATION_STATUSES`, `_PLAN_LOCKS`,
    `active_reserved_cost`, `create_cost_reservation`,
    `mark_reservation_submitted`, `mark_reservation_stale_needs_repair`,
    `settle_reservation`, `release_unsubmitted_reservation`, and
    `expire_unsubmitted_reservations`.
- Modify: `server/app/services/provider_cost_reservation_service.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/video_production/README.md`
  - Documents provider cost reservation service ownership, facade mapping, and
    cleanup gates.
- Create:
  `server/tests/test_video_production_provider_cost_reservation_service_facade.py`
  - Proves provider cost reservation boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create:
  `server/tests/test_video_production_provider_cost_reservation_service_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-provider-cost-reservation-service-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-provider-cost-reservation-service-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain provider cost reservation file exists, the
legacy module is a facade, old and new imports are the same module object,
module-level lock state is shared, the moved helper uses domain production error
and state contract imports, and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_cost_reservation_service_facade.py -q
```

Expected: FAIL because the domain provider cost reservation service does not
exist yet, the old service file still contains helper implementation, and README
does not register the facade.

### Task 2: Move The Reservation Service

**Files:**

- Create:
  `server/app/domains/video_production/provider_cost_reservation_service.py`
- Modify: `server/app/services/provider_cost_reservation_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of
`server/app/services/provider_cost_reservation_service.py` into
`server/app/domains/video_production/provider_cost_reservation_service.py`.

- [ ] **Step 2: Use domain helper imports**

Change the moved implementation to import `ProductionErrorCode` and
`ProductionRepairableError` from
`app.domains.video_production.production_errors`, and cost status constants from
`app.domains.video_production.production_state_contract`.

- [ ] **Step 3: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production provider cost reservations.

The implementation now lives in app.domains.video_production.provider_cost_reservation_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import provider_cost_reservation_service as _provider_cost_reservation_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _provider_cost_reservation_service
globals().update(_provider_cost_reservation_service.__dict__)
```

### Task 3: Update Docs

**Files:**

- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Update README**

Record `app.services.provider_cost_reservation_service` as a facade targeting
`app.domains.video_production.provider_cost_reservation_service`, and add a
cleanup gate requiring only compatibility tests, migration docs, approved
cross-domain consumers, or service modules whose domains have not moved yet to
reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_cost_reservation_service_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_cost_reservation_service_facade.py server/tests/test_provider_cost_reservation_service.py server/tests/test_provider_stage_executor.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move provider cost reservations into domain
```
