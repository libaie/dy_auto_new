# Service Implementation Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automated inventory gates for the remaining implementation files in `server/app/services`.

**Architecture:** A pytest file scans git-tracked direct files in `server/app/services`, treats files importing `app.domains` as compatibility facades, compares the remaining file names with a temporary allowlist, separately tracks mixed facades that still define top-level implementation, and validates a target-domain map for each remaining implementation file.

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

### Task 4: Ignore Untracked Service Drafts

**Files:**

- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Add the failing untracked-file test**

```python
import subprocess


def test_non_facade_inventory_ignores_untracked_files():
    assert _non_facade_service_files() <= _tracked_service_file_names()


def _tracked_service_file_names() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "server/app/services/*.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    return {Path(line).name for line in result.stdout.splitlines()}
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL when the local worktree has an untracked service file such as
`storyboard_image_service.py`.

- [ ] **Step 3: Scan tracked files only**

```python
def _tracked_service_file_names() -> set[str]:
    return {path.name for path in _tracked_service_files()}


def _tracked_service_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--", "server/app/services/*.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines()]
```

Use `_tracked_service_files()` in `_non_facade_service_files()` and
`_mixed_facade_implementation_files()`.

- [ ] **Step 4: Run green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: PASS.

### Task 5: Record Mixed Facade Debt

**Files:**

- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Add the failing mixed-facade test**

```python
import ast

EXPECTED_MIXED_FACADE_SERVICE_FILES = set()


def test_mixed_facade_implementation_inventory_matches_allowlist():
    assert _mixed_facade_implementation_files() == EXPECTED_MIXED_FACADE_SERVICE_FILES


def _mixed_facade_implementation_files() -> set[str]:
    files = set()
    for path in SERVICES_ROOT.glob("*.py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if not _imports_domains(text):
            continue
        tree = ast.parse(text)
        has_top_level_definition = any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            for node in tree.body
        )
        if has_top_level_definition:
            files.add(path.name)
    return files


def _imports_domains(text: str) -> bool:
    return "from app.domains" in text or "import app.domains" in text
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with `video_production_service.py` as the only mixed facade.

- [ ] **Step 3: Record the current mixed facade**

```python
EXPECTED_MIXED_FACADE_SERVICE_FILES = {
    "video_production_service.py",
}
```

- [ ] **Step 4: Run green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: PASS.

### Task 6: Commit

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
git commit --only docs/superpowers/specs/2026-06-20-service-implementation-inventory-design.md docs/superpowers/plans/2026-06-20-service-implementation-inventory-plan.md server/tests/test_service_implementation_inventory.py -m "test: inventory mixed service facades"
```
