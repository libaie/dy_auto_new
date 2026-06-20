# Image Production Cost Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move image production cost event recording into the image generation domain while preserving legacy imports.

**Architecture:** `app.domains.image_generation.image_production_cost_service` becomes the implementation owner. `app.services.image_production_cost_service` becomes a `sys.modules` alias facade. The dirty `image_creation_service` WIP keeps its legacy import as the approved compatibility path for this slice.

**Tech Stack:** Python, SQLAlchemy ORM, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_image_generation_cost_service_facade.py`
- Read: `server/app/services/image_production_cost_service.py`
- Read: `server/app/services/image_creation_service.py`
- Read: `server/app/domains/image_generation/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-production-cost-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-production-cost-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_cost_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/image_production_cost_service.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"
IMAGE_CREATION_SERVICE_PATH = REPO_ROOT / "server/app/services/image_creation_service.py"


def test_image_production_cost_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.image_generation.image_production_cost_service",
        "app.services.image_production_cost_service",
        "record_estimated_cost_event",
        "record_actual_cost_event",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_image_production_cost_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_image_production_cost_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def record_estimated_cost_event" not in text
    assert "def record_actual_cost_event" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_image_production_cost_service_module_is_domain_module():
    legacy = importlib.import_module("app.services.image_production_cost_service")
    domain = importlib.import_module("app.domains.image_generation.image_production_cost_service")
    assert legacy is domain
    assert legacy.record_estimated_cost_event is domain.record_estimated_cost_event
    assert legacy.record_actual_cost_event is domain.record_actual_cost_event


def test_services_parent_package_image_production_cost_attribute_is_domain_module():
    from app.services import image_production_cost_service as parent_import

    domain = importlib.import_module("app.domains.image_generation.image_production_cost_service")
    assert parent_import is domain


def test_image_creation_service_keeps_approved_legacy_cost_import():
    text = IMAGE_CREATION_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.services.image_production_cost_service" in text
    assert "app.domains.image_generation.image_production_cost_service" not in text


def test_image_generation_docs_register_image_production_cost_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.image_generation.image_production_cost_service",
        "app.services.image_production_cost_service",
        "record_estimated_cost_event",
        "approved image creation service compatibility import",
    ]:
        assert term in readme


def test_record_actual_cost_event_stays_legacy_compatible(db):
    from app.db_models import ImageCreationTask, ImageProductionCostEvent
    from app.services.image_production_cost_service import record_actual_cost_event

    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="cost test",
        status="succeeded",
        count=1,
        target_count=1,
        provider="pixelle",
        provider_task_id="provider-1",
        estimated_cost_json={"amount": 1.25, "currency": "CNY", "estimate_source": "policy"},
        provider_response_json={"usage": {"actual_cost": 2.5, "currency": "CNY", "images": 1}},
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    event = record_actual_cost_event(db, task)

    assert event is not None
    assert event.event_type == "actual"
    assert event.actual_cost == 2.5
    assert event.estimated_cost == 1.25
    assert db.query(ImageProductionCostEvent).filter(ImageProductionCostEvent.task_id == task.id).count() == 1


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_cost_service_facade.py -q
```

Expected: FAIL because the domain file, legacy facade, and README registration do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/image_generation/image_production_cost_service.py`
- Modify: `server/app/services/image_production_cost_service.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/image_generation/image_production_cost_service.py
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for image generation cost event helpers."""

import sys

from app.domains.image_generation import image_production_cost_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/image_generation/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `image_production_cost_service.py` owns `record_estimated_cost_event`,
  `record_actual_cost_event`, image generation cost event keys, provider usage
  extraction, and `ImageProductionCostEvent` writes.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.image_production_cost_service` | `app.domains.image_generation.image_production_cost_service` | Keep while `image_creation_service` has an approved image creation service compatibility import; remove only after import inventory shows no production legacy imports. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_cost_service_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run existing cost tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_production_cost_service.py -q
```

Expected: PASS.

- [x] **Step 3: Run image strategy snapshot tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_creation_strategy_snapshot.py -q
```

Expected: PASS.

- [x] **Step 4: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.image_production_cost_service" server/app -g "*.py"
```

Expected: only the approved `server/app/services/image_creation_service.py` compatibility import.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-image-production-cost-domain-design.md docs/superpowers/plans/2026-06-20-image-production-cost-domain-plan.md server/tests/test_image_generation_cost_service_facade.py server/app/domains/image_generation/image_production_cost_service.py server/app/services/image_production_cost_service.py server/app/domains/image_generation/README.md
git commit -m "refactor: move image cost events into image generation"
```
