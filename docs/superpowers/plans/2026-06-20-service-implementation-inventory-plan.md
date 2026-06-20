# Service Implementation Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automated inventory gate for the remaining non-facade implementation files in `server/app/services`.

**Architecture:** A pytest file scans direct files in `server/app/services`, treats files importing `app.domains` as compatibility facades, compares the remaining file names with a temporary allowlist, and validates a target-domain map for each remaining implementation file.

**Tech Stack:** Python stdlib `pathlib`, pytest.

---

### Task 1: Red Inventory Test

**Files:**

- Create: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Add the failing test with an empty allowlist**

```python
EXPECTED_NON_FACADE_SERVICE_FILES = set()
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with the current non-facade implementation files in
`server/app/services`.

### Task 2: Record Current Service Implementation Inventory

**Files:**

- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Replace the empty allowlist with the current discovered files**

Record each file name as a string:

```python
"ai_generator.py"
```

- [ ] **Step 2: Run green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: PASS.

### Task 3: Record Target Domains

**Files:**

- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Add the failing target-domain map test**

```python
EXPECTED_SERVICE_DOMAIN_TARGETS = {}


def test_service_implementation_files_have_target_domains():
    assert set(EXPECTED_SERVICE_DOMAIN_TARGETS) == EXPECTED_NON_FACADE_SERVICE_FILES
    assert all(EXPECTED_SERVICE_DOMAIN_TARGETS.values())
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL because the target-domain map is empty while the allowlist
contains the current service implementation files.

- [ ] **Step 3: Fill the target-domain map and validate domain names**

```python
DOMAINS_ROOT = REPO_ROOT / "server/app/domains"

EXPECTED_SERVICE_DOMAIN_TARGETS = {
    "agency_console.py": "agency_operations",
    "agency_creative_patch_service.py": "agency_operations",
    "agency_debate_audit.py": "agency_operations",
    "agency_orchestrator.py": "agency_operations",
    "agency_repair_executor.py": "agency_operations",
    "agency_runtime.py": "agency_operations",
    "ai_generator.py": "model_configuration",
    "image_creation_service.py": "image_generation",
    "one_sentence_video_service.py": "video_production",
    "production_queue_service.py": "video_production",
    "production_run_service.py": "video_production",
    "production_worker_service.py": "video_production",
    "storyboard_image_service.py": "storyboard_images",
    "video_agency_team.py": "agency_operations",
    "video_production_readiness.py": "video_production",
}


def test_service_implementation_targets_are_existing_domains():
    domain_names = {
        path.name
        for path in DOMAINS_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    assert set(EXPECTED_SERVICE_DOMAIN_TARGETS.values()) <= domain_names
```

- [ ] **Step 4: Run green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: PASS.

### Task 4: Commit

**Files:**

- Add: `docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md`
- Add: `docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md`
- Add: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Run final checks**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
git diff --check -- docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md server/tests/test_service_implementation_inventory.py
```

- [ ] **Step 2: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md server/tests/test_service_implementation_inventory.py
git commit --only docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md server/tests/test_service_implementation_inventory.py -m "test: map service implementation targets"
```
