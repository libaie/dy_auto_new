# Domain Service Import Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automated inventory gate for domain modules that still import legacy `app.services` modules.

**Architecture:** A pytest file walks `server/app/domains`, parses imports with `ast`, and compares discovered service imports with a temporary allowlist. The test is read-only and does not change runtime behavior.

**Tech Stack:** Python stdlib `ast`, `pathlib`, pytest.

---

### Task 1: Red Inventory Test

**Files:**

- Create: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Add the failing test with an empty allowlist**

```python
EXPECTED_DOMAIN_SERVICE_IMPORTS = set()
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py -q
```

Expected: FAIL with the currently discovered domain imports from `app.services`.

### Task 2: Record Current Inventory

**Files:**

- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Replace the empty allowlist with the current discovered imports**

Record each entry as:

```python
("server/app/domains/example/module.py", "legacy_service_module")
```

- [ ] **Step 2: Run green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py -q
```

Expected: PASS.

### Task 3: Commit

**Files:**

- Add: `docs/superpowers/specs/2026-06-20-domain-service-import-inventory-design.md`
- Add: `docs/superpowers/plans/2026-06-20-domain-service-import-inventory-plan.md`
- Add: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Run final checks**

```powershell
git diff --check -- docs/superpowers/specs/2026-06-20-domain-service-import-inventory-design.md docs/superpowers/plans/2026-06-20-domain-service-import-inventory-plan.md server/tests/test_domain_service_import_inventory.py
```

- [ ] **Step 2: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-domain-service-import-inventory-design.md docs/superpowers/plans/2026-06-20-domain-service-import-inventory-plan.md server/tests/test_domain_service_import_inventory.py
git commit --only docs/superpowers/specs/2026-06-20-domain-service-import-inventory-design.md docs/superpowers/plans/2026-06-20-domain-service-import-inventory-plan.md server/tests/test_domain_service_import_inventory.py -m "test: inventory domain service imports"
```
