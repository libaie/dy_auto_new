# Service Implementation Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automated inventory gate for the remaining non-facade implementation files in `server/app/services`.

**Architecture:** A pytest file scans direct files in `server/app/services`, treats files importing `app.domains` as compatibility facades, and compares the remaining file names with a temporary allowlist.

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

### Task 3: Commit

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
git commit --only docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md server/tests/test_service_implementation_inventory.py -m "test: inventory service implementation files"
```
