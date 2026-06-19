# Video Library Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `app.domains.video_library` and move generated-video library route ownership behind a compatibility-preserving domain module.

**Architecture:** Keep `GeneratedVideo` persistence and current route behavior unchanged while moving only the FastAPI router boundary. Preserve `app.routers.videos` as a thin module alias until import inventory proves it can be removed.

**Tech Stack:** FastAPI `APIRouter`, Pydantic response models, pytest route snapshots, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary, Route Snapshot, And API Contract Tests

**Files:**
- Create: `server/tests/test_video_library_auth_parity.py`
- Create: `server/tests/test_video_library_api.py`
- Create: `server/tests/test_video_library_domain_boundary.py`
- Create: `server/tests/test_video_library_router_facade.py`

- [ ] **Step 1: Write the failing route/auth snapshot test**

```python
from fastapi.routing import APIRoute

from app.main import app


EXPECTED_VIDEO_LIBRARY_HTTP_ROUTES = [
    ("/api/videos", ("GET",), "list_videos", "app.domains.video_library.videos_router.list_videos", ("get_db", "verify_admin_token")),
    ("/api/videos/{video_id}", ("GET",), "get_video", "app.domains.video_library.videos_router.get_video", ("get_db", "verify_admin_token")),
    ("/api/videos/{video_id}/download", ("GET",), "download_video", "app.domains.video_library.videos_router.download_video", ("get_db",)),
    ("/api/videos/{video_id}", ("DELETE",), "delete_video", "app.domains.video_library.videos_router.delete_video", ("get_db", "verify_admin_token")),
]


def test_video_library_route_table_snapshot():
    assert _video_library_http_routes() == EXPECTED_VIDEO_LIBRARY_HTTP_ROUTES
```

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_library_auth_parity.py -q`

Expected: FAIL because endpoints still come from `app.routers.videos`.

- [ ] **Step 2: Add API behavior tests**

Cover list filtering, detail 404, download auth failure, and delete removing the
database row plus local file. These tests document behavior and should continue
passing before and after the move.

- [ ] **Step 3: Add boundary and facade tests**

The tests must assert:

- the spec and plan mention `app.domains.video_library`, `videos_router.py`,
  `app.routers.videos`, `/api/videos`, `app.routers.video_production`, Pixelle,
  and Seedance;
- `app.domains.video_library` exports `DOMAIN_NAME = "video_library"` and
  `PUBLIC_ROUTE_PREFIX = "/api/videos"`;
- `server/app/domains/video_library/README.md` documents the facade register and
  cleanup gates;
- `server/app/routers/videos.py` is a thin facade with no `APIRouter(`;
- `app.main` directly imports and includes `videos_router`;
- video production/provider routers are not imported from this domain;
- legacy and domain module imports resolve to the same object.

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_library_auth_parity.py server/tests/test_video_library_api.py server/tests/test_video_library_domain_boundary.py server/tests/test_video_library_router_facade.py -q`

Expected: FAIL until `app.domains.video_library` and direct main wiring exist.

### Task 2: Domain Skeleton And Facade Register

**Files:**
- Create: `server/app/domains/video_library/__init__.py`
- Create: `server/app/domains/video_library/README.md`

- [ ] **Step 1: Add domain metadata**

```python
"""Video library domain package."""

DOMAIN_NAME = "video_library"
PUBLIC_ROUTE_PREFIX = "/api/videos"
```

- [ ] **Step 2: Add README boundary notes**

Document owned `/api/videos/*` routes, non-owned video production/provider
routes, the `app.routers.videos` facade, stable ORM dependencies, and
compatibility cleanup gates.

### Task 3: Router Move With Compatibility Facade

**Files:**
- Create: `server/app/domains/video_library/videos_router.py`
- Modify: `server/app/routers/videos.py`

- [ ] **Step 1: Copy the router implementation**

Copy the current contents of `server/app/routers/videos.py` to
`server/app/domains/video_library/videos_router.py` without changing route
behavior.

- [ ] **Step 2: Replace legacy router with a module alias**

```python
"""Compatibility facade for video library routes.

The implementation now lives in app.domains.video_library.videos_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_library import videos_router as _videos_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _videos_router
globals().update(_videos_router.__dict__)
```

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_library_auth_parity.py server/tests/test_video_library_api.py server/tests/test_video_library_domain_boundary.py server/tests/test_video_library_router_facade.py -q`

Expected: Auth parity still fails until `app.main` wires the domain router
directly; facade and API behavior tests should pass.

- [ ] **Step 4: Commit**

Run: `git commit -m "refactor: move video library router into domain"`

### Task 4: Direct App Wiring

**Files:**
- Modify: `server/app/main.py`
- Modify: `server/tests/test_video_library_domain_boundary.py`

- [ ] **Step 1: Wire app main to the domain router**

Replace the legacy `videos` router import/include with:

```python
from app.domains.video_library import videos_router
app.include_router(videos_router.router)
```

- [ ] **Step 2: Keep legacy facade for old imports**

Do not remove `server/app/routers/videos.py` in this task.

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_library_auth_parity.py server/tests/test_video_library_api.py server/tests/test_video_library_domain_boundary.py server/tests/test_video_library_router_facade.py -q`

Expected: PASS.

- [ ] **Step 4: Commit**

Use an isolated Git index for `server/app/main.py` if the real worktree has
unrelated changes, then commit:

Run: `git commit -m "refactor: wire video library router from domain"`

### Later Splits

- Split file-delete safety and download token parsing only after route ownership
  is stable.
- Keep `video_production`, Pixelle, and Seedance routes in their own future
  domain slices.

### Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_library_auth_parity.py server/tests/test_video_library_api.py server/tests/test_video_library_domain_boundary.py server/tests/test_video_library_router_facade.py -q
```

Self-review checklist:

- Every `/api/videos/*` endpoint module is
  `app.domains.video_library.videos_router`.
- `app.routers.videos` and `app.domains.video_library.videos_router` are the
  same module object during the facade phase.
- Video production/provider routes remain outside `video_library`.
- No response shape, route path, route name, auth dependency, download token
  fallback, or delete behavior changed.
