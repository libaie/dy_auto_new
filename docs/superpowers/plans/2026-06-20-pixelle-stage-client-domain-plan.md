# Pixelle Stage Client Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Pixelle stage API helper into the Pixelle integration domain while preserving legacy imports.

**Architecture:** `app.domains.pixelle_integration.pixelle_stage_client` becomes the implementation owner. `app.services.pixelle_stage_client` becomes a `sys.modules` alias facade. Dirty legacy orchestration services keep their existing imports for this slice.

**Tech Stack:** Python, SQLAlchemy ORM session type hints, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_pixelle_integration_stage_client_facade.py`
- Read: `server/app/services/pixelle_stage_client.py`
- Read: `server/app/domains/pixelle_integration/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-pixelle-stage-client-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-pixelle-stage-client-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/pixelle_stage_client.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/pixelle_stage_client.py"
README_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/README.md"


def test_pixelle_stage_client_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.pixelle_integration.pixelle_stage_client",
        "app.services.pixelle_stage_client",
        "submit_image_batch",
        "submit_compose",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_pixelle_stage_client_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_pixelle_stage_client_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.pixelle_integration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "async def submit_image_batch" not in text
    assert "async def submit_compose" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_pixelle_stage_client_module_is_domain_module():
    legacy = importlib.import_module("app.services.pixelle_stage_client")
    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_stage_client")
    assert legacy is domain
    assert legacy.submit_image_batch is domain.submit_image_batch
    assert legacy.submit_compose is domain.submit_compose


def test_services_parent_package_pixelle_stage_client_attribute_is_domain_module():
    from app.services import pixelle_stage_client as parent_import

    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_stage_client")
    assert parent_import is domain


def test_domain_stage_client_imports_domain_pixelle_client():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "app.domains.pixelle_integration.pixelle_client" in text
    assert "app.services.pixelle_client" not in text


def test_pixelle_integration_docs_register_pixelle_stage_client_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "pixelle_stage_client.py",
        "app.services.pixelle_stage_client",
        "submit_image_batch",
        "approved compatibility imports",
    ]:
        assert term in readme


@pytest.mark.asyncio
async def test_stage_client_stays_legacy_monkeypatch_compatible(monkeypatch):
    legacy = importlib.import_module("app.services.pixelle_stage_client")
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-1"}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    result = await legacy.submit_image_batch(
        db=None,
        run_id="run-1",
        episode_id="episode-1",
        frames=[{"frame_id": "frame-1"}],
        model_config={"provider": "mock"},
    )

    assert result["stage_task_id"] == "stage-1"
    assert calls == [
        (
            "POST",
            "/api/stages/images/batch",
            {
                "external_run_id": "run-1",
                "episode_id": "episode-1",
                "frames": [{"frame_id": "frame-1"}],
                "model_config": {"provider": "mock"},
                "template_config": {},
            },
        )
    ]


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_integration_stage_client_facade.py -q
```

Expected: FAIL because the domain file, facade, direct domain import, and README registration are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/pixelle_integration/pixelle_stage_client.py`
- Modify: `server/app/services/pixelle_stage_client.py`

- [x] **Step 1: Move implementation**

Copy the current service body into:

```text
server/app/domains/pixelle_integration/pixelle_stage_client.py
```

- [x] **Step 2: Update the domain import**

In the domain module, replace:

```python
from app.services.pixelle_client import _pixelle_request
```

with:

```python
from app.domains.pixelle_integration.pixelle_client import _pixelle_request
```

- [x] **Step 3: Replace legacy module with facade**

```python
"""Compatibility facade for Pixelle stage client helpers."""

import sys

from app.domains.pixelle_integration import pixelle_stage_client as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/pixelle_integration/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `pixelle_stage_client.py` owns Pixelle stage payload construction for image
  batch, image create, stage status, video batch, and compose calls.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.pixelle_stage_client` | `app.domains.pixelle_integration.pixelle_stage_client` | Keep while legacy orchestration services have approved compatibility imports; remove only after import inventory shows no production legacy imports. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_integration_stage_client_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run existing Pixelle stage client tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_stage_client.py server/tests/test_image_creation_pixelle_client.py server/tests/test_video_production_compose.py -q
```

Expected: PASS.

- [x] **Step 3: Run app import smoke**

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: prints the app title.

- [x] **Step 4: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.pixelle_stage_client" server/app -g "*.py"
```

Expected: only not-yet-moved legacy orchestration services keep approved compatibility imports.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-pixelle-stage-client-domain-design.md docs/superpowers/plans/2026-06-20-pixelle-stage-client-domain-plan.md server/tests/test_pixelle_integration_stage_client_facade.py server/app/domains/pixelle_integration/pixelle_stage_client.py server/app/services/pixelle_stage_client.py server/app/domains/pixelle_integration/README.md
git commit -m "refactor: move pixelle stage client into pixelle integration"
```
