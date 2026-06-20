# AI Generator Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move shared AI generation helpers into `model_configuration` while preserving the legacy service import.

**Architecture:** `app.domains.model_configuration.ai_generator` owns `AiGeneratorService` and the shared `ai_generator` instance. `app.services.ai_generator` aliases the domain module until callers move to the domain path.

**Tech Stack:** Python, httpx, pytest.

---

### Task 1: Inventory Red

**Files:**
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Remove `ai_generator.py` from the service implementation allowlist**

```python
EXPECTED_NON_FACADE_SERVICE_FILES = {
    "agency_console.py",
    "agency_orchestrator.py",
    "image_creation_service.py",
    "one_sentence_video_service.py",
    "production_run_service.py",
    "production_worker_service.py",
    "video_agency_team.py",
}
```

Also remove the `"ai_generator.py": "model_configuration"` entry from
`EXPECTED_SERVICE_DOMAIN_TARGETS`.

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with `ai_generator.py` as an extra non-facade service file.

### Task 2: Move Generator

**Files:**
- Create: `server/app/domains/model_configuration/ai_generator.py`
- Modify: `server/app/services/ai_generator.py`
- Modify: `server/app/domains/model_configuration/README.md`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation**

Move the current implementation from `server/app/services/ai_generator.py` to
`server/app/domains/model_configuration/ai_generator.py`.

- [ ] **Step 2: Point content filtering at the content domain**

Use this import in the moved file:

```python
from app.domains.content_collection.content_service import content_service
```

- [ ] **Step 3: Replace the legacy service with this facade**

```python
"""Compatibility facade for AI generation helpers."""

from __future__ import annotations

import sys

from app.domains.model_configuration import ai_generator as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 4: Update README registration**

Add `ai_generator.py` to Current Modules and add this facade row:

```markdown
| `app.services.ai_generator` | `app.domains.model_configuration.ai_generator` | Keep while app startup/shutdown, domain callers, and legacy tests import or monkeypatch the shared generator through `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 5: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_ai_generator.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-ai-generator-domain-design.md docs/superpowers/plans/2026-06-20-ai-generator-domain-plan.md server/tests/test_service_implementation_inventory.py server/app/domains/model_configuration/ai_generator.py server/app/services/ai_generator.py server/app/domains/model_configuration/README.md
git commit --only docs/superpowers/specs/2026-06-20-ai-generator-domain-design.md docs/superpowers/plans/2026-06-20-ai-generator-domain-plan.md server/tests/test_service_implementation_inventory.py server/app/domains/model_configuration/ai_generator.py server/app/services/ai_generator.py server/app/domains/model_configuration/README.md -m "refactor: move ai generator into domain"
```
