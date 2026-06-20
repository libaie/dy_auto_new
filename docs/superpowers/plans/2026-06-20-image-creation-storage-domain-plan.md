# Image Creation Storage Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move image upload/output storage helpers into the image generation domain while preserving legacy imports.

**Architecture:** `app.domains.image_generation.image_creation_storage` becomes the implementation owner. `app.services.image_creation_storage` becomes a `sys.modules` alias facade. Clean domain callers import the domain helper directly, while `image_creation_service` keeps the legacy path as an approved WIP compatibility import.

**Tech Stack:** Python, pathlib, FastAPI `UploadFile`, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_image_generation_creation_storage_facade.py`
- Read: `server/app/services/image_creation_storage.py`
- Read: `server/app/domains/image_generation/image_creation_router.py`
- Read: `server/app/domains/creative_library/reference_asset_service.py`
- Read: `server/app/services/image_creation_service.py`
- Read: `server/app/domains/image_generation/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-creation-storage-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-creation-storage-domain-plan.md"
DOMAIN_STORAGE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_creation_storage.py"
LEGACY_STORAGE_PATH = REPO_ROOT / "server/app/services/image_creation_storage.py"
IMAGE_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_creation_router.py"
REFERENCE_ASSET_PATH = REPO_ROOT / "server/app/domains/creative_library/reference_asset_service.py"
IMAGE_CREATION_SERVICE_PATH = REPO_ROOT / "server/app/services/image_creation_service.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_creation_storage_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.image_generation.image_creation_storage",
        "app.services.image_creation_storage",
        "save_output_bytes",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_image_creation_storage_domain_file_exists():
    assert DOMAIN_STORAGE_PATH.exists()


def test_legacy_image_creation_storage_is_thin_facade():
    text = LEGACY_STORAGE_PATH.read_text(encoding="utf-8")
    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def save_output_bytes" not in text
    assert "def save_upload" not in text
    assert _line_count(LEGACY_STORAGE_PATH) <= 12


def test_legacy_image_creation_storage_module_is_domain_module():
    legacy = importlib.import_module("app.services.image_creation_storage")
    domain = importlib.import_module("app.domains.image_generation.image_creation_storage")
    assert legacy is domain
    assert legacy.save_output_bytes is domain.save_output_bytes
    assert legacy.save_upload is domain.save_upload
    assert legacy.configured_public_base_url is domain.configured_public_base_url
    assert legacy.IMAGE_CREATION_ROOT is domain.IMAGE_CREATION_ROOT


def test_services_parent_package_image_creation_storage_attribute_is_domain_module():
    from app.services import image_creation_storage as parent_import

    domain = importlib.import_module("app.domains.image_generation.image_creation_storage")
    assert parent_import is domain


def test_image_creation_storage_root_stays_under_app_static():
    domain = importlib.import_module("app.domains.image_generation.image_creation_storage")
    assert domain.IMAGE_CREATION_ROOT == REPO_ROOT / "server/app/static/image-creation"


def test_domain_callers_import_domain_storage_only():
    for path in [IMAGE_ROUTER_PATH, REFERENCE_ASSET_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.image_generation.image_creation_storage" in text
        assert "app.services.image_creation_storage" not in text


def test_image_creation_service_stays_legacy_compatible_for_wip_slice():
    text = IMAGE_CREATION_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.services.image_creation_storage" in text
    assert "app.domains.image_generation.image_creation_storage" not in text


def test_image_generation_docs_register_image_creation_storage_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.image_generation.image_creation_storage",
        "app.services.image_creation_storage",
        "save_output_bytes",
        "approved image creation service compatibility import",
    ]:
        assert term in readme


def test_save_output_bytes_stays_legacy_compatible(tmp_path, monkeypatch):
    legacy = importlib.import_module("app.services.image_creation_storage")
    monkeypatch.setattr(legacy, "IMAGE_CREATION_ROOT", tmp_path / "image-creation")
    saved = legacy.save_output_bytes(
        b"fake image",
        "https://cdn.example.test",
        content_type="image/png",
    )
    assert saved["url"].startswith("https://cdn.example.test/static/image-creation/outputs/")
    assert saved["storage_path"].startswith("outputs/")
    assert Path(saved["local_path"]).read_bytes() == b"fake image"
    assert saved["mime_type"] == "image/png"


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_creation_storage_facade.py -q
```

Expected: FAIL because the domain file, facade, corrected root, and direct domain imports are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/image_generation/image_creation_storage.py`
- Modify: `server/app/services/image_creation_storage.py`
- Modify: `server/app/domains/image_generation/image_creation_router.py`
- Modify: `server/app/domains/creative_library/reference_asset_service.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/image_generation/image_creation_storage.py
```

Use this storage root from the new location:

```python
IMAGE_CREATION_ROOT = Path(__file__).resolve().parents[2] / "static" / "image-creation"
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for image generation storage helpers."""

import sys

from app.domains.image_generation import image_creation_storage as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update clean domain imports**

Replace `from app.services.image_creation_storage import ...` with:

```python
from app.domains.image_generation.image_creation_storage import ...
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/image_generation/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `image_creation_storage.py` owns `IMAGE_CREATION_ROOT`, upload/output image storage, public image URLs, and image storage content-type/size validation.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.image_creation_storage` | `app.domains.image_generation.image_creation_storage` | Keep while `image_creation_service` has an approved image creation service compatibility import; remove only after import inventory shows no production legacy imports. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_creation_storage_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run image upload/storage tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_creation_api.py -q
```

Expected: PASS.

- [x] **Step 3: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.image_creation_storage" server/app -g "*.py"
```

Expected: only the approved `server/app/services/image_creation_service.py` compatibility import.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-image-creation-storage-domain-design.md docs/superpowers/plans/2026-06-20-image-creation-storage-domain-plan.md server/tests/test_image_generation_creation_storage_facade.py server/app/domains/image_generation/image_creation_storage.py server/app/services/image_creation_storage.py server/app/domains/image_generation/image_creation_router.py server/app/domains/creative_library/reference_asset_service.py server/app/domains/image_generation/README.md
git commit -m "refactor: move image storage into image generation"
```
