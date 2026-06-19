# Video Production Provider Capability Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move provider capability policy into the video production domain while
preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.video_production.provider_capability_service`.
`app.services.provider_capability_service` becomes a `sys.modules` facade so old
callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create:
  `server/app/domains/video_production/provider_capability_service.py`
  - Owns `DEFAULT_REAL_PROVIDER_CAPABILITY`, `capability_from_model_config`,
    and `assert_real_paid_allowed`.
- Modify: `server/app/services/provider_capability_service.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/video_production/README.md`
  - Documents provider capability service ownership, facade mapping, and cleanup
    gates.
- Create:
  `server/tests/test_video_production_provider_capability_service_facade.py`
  - Proves capability helper boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create:
  `server/tests/test_video_production_provider_capability_service_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-provider-capability-service-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-provider-capability-service-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain capability service file exists, the legacy
module is a facade, old and new imports are the same module object, the moved
helper uses the domain production errors import, and README cleanup gates
document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_capability_service_facade.py -q
```

Expected: FAIL because the domain capability service does not exist yet, the old
service file still contains helper implementation, and README does not register
the facade.

### Task 2: Move The Capability Service

**Files:**

- Create:
  `server/app/domains/video_production/provider_capability_service.py`
- Modify: `server/app/services/provider_capability_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of
`server/app/services/provider_capability_service.py` into
`server/app/domains/video_production/provider_capability_service.py`.

- [ ] **Step 2: Use domain production error imports**

Change the moved implementation to import `ProductionErrorCode` and
`ProductionRepairableError` from
`app.domains.video_production.production_errors`.

- [ ] **Step 3: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production provider capability helpers.

The implementation now lives in app.domains.video_production.provider_capability_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import provider_capability_service as _provider_capability_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _provider_capability_service
globals().update(_provider_capability_service.__dict__)
```

### Task 3: Update Docs

**Files:**

- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Update README**

Record `app.services.provider_capability_service` as a facade targeting
`app.domains.video_production.provider_capability_service`, and add a cleanup
gate requiring only compatibility tests, migration docs, approved cross-domain
consumers, or service modules whose domains have not moved yet to reference the
legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_capability_service_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_capability_service_facade.py server/tests/test_provider_stage_executor.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move provider capability helper into domain
```
