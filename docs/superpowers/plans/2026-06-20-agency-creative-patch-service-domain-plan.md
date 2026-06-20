# Agency Creative Patch Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency creative patch mutation logic into `app.domains.agency_operations`.

**Architecture:** The domain module owns the implementation. The old `app.services.agency_creative_patch_service` path stays as a module alias for compatibility.

**Tech Stack:** Python stdlib, FastAPI, SQLAlchemy, pytest.

---

### Task 1: Red Inventory

**Files:**

- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Scan committed service files only**

```python
def _committed_service_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", "server/app/services"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line.endswith(".py")]
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL because the allowlist still includes staged-only service files
`agency_creative_patch_service.py` and `agency_debate_audit.py`.

### Task 2: Move Creative Patch Service

**Files:**

- Move: `server/app/services/agency_creative_patch_service.py` to `server/app/domains/agency_operations/agency_creative_patch_service.py`
- Create: `server/app/services/agency_creative_patch_service.py`
- Modify: `server/app/domains/agency_operations/agency_persistence.py`
- Modify: `server/app/domains/agency_operations/agency_router.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation file**

```powershell
Move-Item -LiteralPath 'server/app/services/agency_creative_patch_service.py' -Destination 'server/app/domains/agency_operations/agency_creative_patch_service.py'
```

- [ ] **Step 2: Import the domain service from agency modules**

```python
from app.domains.agency_operations.agency_creative_patch_service import create_patches_for_invocation
```

```python
from app.domains.agency_operations.agency_creative_patch_service import (
    apply_approved_patches,
    apply_patch as apply_creative_patch,
    approve_patch as approve_creative_patch,
    creative_patch_summary,
    reject_patch as reject_creative_patch,
    update_patch_after,
)
```

- [ ] **Step 3: Add the compatibility alias**

```python
from __future__ import annotations

import sys

from app.domains.agency_operations import agency_creative_patch_service as _impl

sys.modules[__name__] = _impl
```

- [ ] **Step 4: Update inventories**

Remove these entries from `EXPECTED_DOMAIN_SERVICE_IMPORTS`:

```python
("server/app/domains/agency_operations/agency_persistence.py", "agency_creative_patch_service"),
("server/app/domains/agency_operations/agency_router.py", "agency_creative_patch_service"),
```

Remove these entries from `EXPECTED_NON_FACADE_SERVICE_FILES` and
`EXPECTED_SERVICE_DOMAIN_TARGETS`:

```python
"agency_creative_patch_service.py"
"agency_debate_audit.py"
```

### Task 3: Verify And Commit

**Files:**

- Add: `docs/superpowers/specs/2026-06-20-agency-creative-patch-service-domain-design.md`
- Add: `docs/superpowers/plans/2026-06-20-agency-creative-patch-service-domain-plan.md`
- Modify: `docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md`
- Modify: `docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md`
- Add: `server/app/domains/agency_operations/agency_creative_patch_service.py`
- Modify: `server/app/domains/agency_operations/agency_persistence.py`
- Modify: `server/app/domains/agency_operations/agency_router.py`
- Modify: `server/app/domains/agency_operations/README.md`
- Add: `server/app/services/agency_creative_patch_service.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Run final checks**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py server/tests/test_domain_service_import_inventory.py server/tests/test_agency_creative_patch_service.py server/tests/test_agency_creative_patch_api.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

- [ ] **Step 2: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-creative-patch-service-domain-design.md docs/superpowers/plans/2026-06-20-agency-creative-patch-service-domain-plan.md docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md server/app/domains/agency_operations/agency_creative_patch_service.py server/app/domains/agency_operations/agency_persistence.py server/app/domains/agency_operations/agency_router.py server/app/domains/agency_operations/README.md server/app/services/agency_creative_patch_service.py server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py
git commit --only docs/superpowers/specs/2026-06-20-agency-creative-patch-service-domain-design.md docs/superpowers/plans/2026-06-20-agency-creative-patch-service-domain-plan.md docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md server/app/domains/agency_operations/agency_creative_patch_service.py server/app/domains/agency_operations/agency_persistence.py server/app/domains/agency_operations/agency_router.py server/app/domains/agency_operations/README.md server/app/services/agency_creative_patch_service.py server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py -m "refactor: move agency creative patch service into domain"
```
