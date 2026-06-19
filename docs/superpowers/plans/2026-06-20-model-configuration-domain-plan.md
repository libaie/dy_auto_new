# Model Configuration Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `/api/ai-models/*` and model seeding helpers into `app.domains.model_configuration` while preserving legacy imports.

**Architecture:** This is a facade-first router migration. The current `app.routers.ai_config` code becomes `app.domains.model_configuration.ai_models_router`; the old module path becomes a `sys.modules` facade, and `app.main` imports the domain router and seed helper directly.

**Tech Stack:** FastAPI, pytest, SQLAlchemy `AIModel`, existing crypto and model schema services.

---

## File Structure

- Create `server/app/domains/model_configuration/__init__.py`: domain metadata.
- Create `server/app/domains/model_configuration/README.md`: owned routes, non-owned services, facade, and cleanup gates.
- Create `server/app/domains/model_configuration/ai_models_router.py`: moved implementation from `server/app/routers/ai_config.py`.
- Modify `server/app/routers/ai_config.py`: compatibility facade pointing at the domain module.
- Modify `server/app/main.py`: import `ai_models_router` and `seed_ai_models` from the domain.
- Create `server/tests/test_model_configuration_domain_boundary.py`: spec, README, facade, main wiring, and import smoke tests.
- Create `server/tests/test_model_configuration_router_facade.py`: legacy/domain module identity and router snapshot.
- Create `server/tests/test_model_configuration_auth_parity.py`: FastAPI route table snapshot.

The move preserves `AIModel` CRUD behavior, `ModelCreate`, `ModelUpdate`,
`DEFAULT_MODELS`, `seed_ai_models`, blank-secret preservation, SSRF guard
behavior, provider test strategies, and legacy `app.routers.ai_config`
monkeypatch compatibility.

### Task 1: Write Spec, Plan, And Red Boundary Tests

**Files:**
- Create: `docs/superpowers/specs/2026-06-20-model-configuration-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-model-configuration-domain-plan.md`
- Create: `server/tests/test_model_configuration_domain_boundary.py`
- Create: `server/tests/test_model_configuration_router_facade.py`
- Create: `server/tests/test_model_configuration_auth_parity.py`

- [ ] **Step 1: Write failing tests**

```python
EXPECTED_MODEL_CONFIGURATION_ROUTES = [
    ("GET", "/api/ai-models", "list_models"),
    ("GET", "/api/ai-models/options", "get_options"),
    ("GET", "/api/ai-models/schema", "get_schema"),
    ("GET", "/api/ai-models/{model_id}", "get_model"),
    ("POST", "/api/ai-models", "create_model"),
    ("PUT", "/api/ai-models/{model_id}", "update_model"),
    ("DELETE", "/api/ai-models/{model_id}", "delete_model"),
    ("POST", "/api/ai-models/{model_id}/test", "test_connection"),
]
```

The tests expect `app.domains.model_configuration.ai_models_router` to exist,
`app.routers.ai_config` to be a facade, and `app.main` to register endpoints
from `app.domains.model_configuration.ai_models_router`.

- [ ] **Step 2: Run red tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_model_configuration_domain_boundary.py tests/test_model_configuration_router_facade.py tests/test_model_configuration_auth_parity.py -q
```

Expected: FAIL because `app.domains.model_configuration` does not exist and
`app.main` still wires `app.routers.ai_config`.

### Task 2: Move Router Into Domain And Keep Facade

**Files:**
- Create: `server/app/domains/model_configuration/__init__.py`
- Create: `server/app/domains/model_configuration/README.md`
- Create: `server/app/domains/model_configuration/ai_models_router.py`
- Modify: `server/app/routers/ai_config.py`

- [ ] **Step 1: Create domain metadata**

```python
"""Model configuration domain package."""

DOMAIN_NAME = "model_configuration"
PUBLIC_ROUTE_PREFIX = "/api/ai-models"
```

- [ ] **Step 2: Move implementation**

Copy the full current implementation from `server/app/routers/ai_config.py` to
`server/app/domains/model_configuration/ai_models_router.py` without changing
route logic, default model constants, or seed behavior.

- [ ] **Step 3: Replace legacy module with facade**

```python
"""Compatibility facade for model configuration routes.

The implementation now lives in app.domains.model_configuration.ai_models_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.model_configuration import ai_models_router as _ai_models_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _ai_models_router
globals().update(_ai_models_router.__dict__)
```

### Task 3: Wire Main Directly To The Domain

**Files:**
- Modify: `server/app/main.py`

- [ ] **Step 1: Update imports**

Add:

```python
from app.domains.model_configuration import ai_models_router
from app.domains.model_configuration.ai_models_router import seed_ai_models
```

Remove `ai_config` from the `from app.routers import ...` import list.

- [ ] **Step 2: Update startup seed import**

Remove the local startup import:

```python
from app.routers.ai_config import seed_ai_models
```

Keep the call:

```python
seed_ai_models(db)
```

- [ ] **Step 3: Update include_router call**

Replace:

```python
app.include_router(ai_config.router)
```

with:

```python
app.include_router(ai_models_router.router)
```

### Task 4: Verify And Commit

**Files:**
- All files above.

- [ ] **Step 1: Run focused tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_model_configuration_domain_boundary.py tests/test_model_configuration_router_facade.py tests/test_model_configuration_auth_parity.py tests/test_ai_config_scene_schema.py tests/test_image_creation_model_resolution.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Commit with isolated `main.py` staging**

Because `server/app/main.py` may contain unrelated local WIP, stage only the
model-configuration import/include/seed changes through an isolated temporary
index. Do not stage unrelated `main.py` changes.

Commit message:

```powershell
git commit -m "refactor: move model configuration router into domain"
```

### Self-Review

- The spec covers ownership, non-ownership, compatibility, tests, and cleanup
  gates.
- The plan covers each file and exact verification commands.
- The migration preserves current route behavior and seed helpers.
