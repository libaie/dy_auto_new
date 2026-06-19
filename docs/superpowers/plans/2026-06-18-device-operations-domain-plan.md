# Device Operations Domain Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move device pairing, websocket status, task polling, content generation, collection reports, DM claims, and asset upload endpoints out of the flat device router after the `ai_video_series` facade pattern is proven.

**Architecture:** Start with behavior-neutral boundary tests and auth characterization for `server/app/routers/device.py`, then move the router under `app.domains.device_operations` with legacy module identity, split polling/reporting/upload use cases, and add cleanup gates. `device_operations` owns the `/api/device/*` transport surface and the admin `/api/devices/*` pairing surface. Content, collection, and DM business behavior may first move as device-authenticated adapters, but final content ownership belongs to the separate `content_collection` child plan.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pytest, existing task/device/account services.

---

## First Tasks

- [ ] Characterize current `/api/device/*` and `/api/devices/*` route methods, websocket paths, and auth dependencies.
- [ ] Create `server/app/domains/device_operations`.
- [ ] Move `app.routers.device` and `app.routers.devices` behind compatibility module aliases.
- [ ] Split device pairing, status websocket, polling, reporting, upload, and bridge handlers into focused modules.
- [ ] Add facade cleanup gates before removing old imports.

## File Map

### New Domain Files

- `server/app/domains/device_operations/__init__.py`
  - Exports `DOMAIN_NAME = "device_operations"` and public route prefixes `("/api/device", "/api/devices")`.
- `server/app/domains/device_operations/README.md`
  - Facade register, domain ownership rules, route/auth snapshots, cleanup gates, and verification commands.
- `server/app/domains/device_operations/device_router.py`
  - Owns `/api/device/*` route assembly after the compatibility move.
- `server/app/domains/device_operations/admin_router.py`
  - Owns `/api/devices/*` route assembly and pairing-event websocket after the compatibility move.
- `server/app/domains/device_operations/schemas.py`
  - Owns request/response models currently embedded in `server/app/routers/device.py` and `server/app/routers/devices.py`.
- `server/app/domains/device_operations/pairing.py`
  - Owns pair request creation, pair status lookup, pair websocket lifecycle, and admin approve/reject orchestration.
- `server/app/domains/device_operations/status_ws.py`
  - Owns `/api/device/ws/status`, in-memory status connection tracking, heartbeat state, and offline detection boundaries.
- `server/app/domains/device_operations/status_lifecycle.py`
  - Owns the extracted offline checker use case after it moves out of `server/app/main.py::_offline_checker`, including heartbeat flushes, offline marking, admin broadcasts, and stuck task handling.
- `server/app/domains/device_operations/polling.py`
  - Owns `/api/device/poll`, task lease selection, task response shaping, and device-secret authorization assumptions.
- `server/app/domains/device_operations/reporting.py`
  - Owns `/api/device/progress`, `/api/device/report`, `/api/device/stats/increment`, `/api/device/heartbeat`, and `/api/device/risk-report`.
- `server/app/domains/device_operations/script_assets.py`
  - Owns selector/template/script version/download/upload endpoints and any filesystem or asset-storage adapter calls used by device clients.
- `server/app/domains/device_operations/content_bridge.py`
  - Temporary bridge for `/api/device/generate-content`, `/api/device/comment-ai-reply`, collection reports, user profile/avatar reports, and DM claim/report/release endpoints until `content_collection` takes the business use cases.
- `server/app/domains/device_operations/adapters.py`
  - Narrow adapter layer over `app.services.device_service`, `app.services.task_service`, `app.services.content_service`, AI generation helpers, and persistence currently called directly from the routers.

### Compatibility Facades To Modify In Future PRs

- `server/app/routers/device.py`
  - Becomes a compatibility alias to `app.domains.device_operations.device_router`.
- `server/app/routers/devices.py`
  - Becomes a compatibility alias to `app.domains.device_operations.admin_router`.
- `server/app/main.py`
  - Must continue importing routers through the legacy modules until the cleanup gate explicitly moves imports to domain modules.
  - Current `server/app/main.py::_offline_checker` and lifespan `asyncio.create_task(_offline_checker())` are part of the device operations boundary and must be characterized before moving lifecycle behavior.

### New Tests

- `server/tests/test_device_operations_auth_parity.py`
  - Snapshots `/api/device/*` and `/api/devices/*` route methods, websocket paths, dependencies, and device-secret/admin-token split.
- `server/tests/test_device_operations_domain_boundary.py`
  - Verifies domain package metadata, README facade register, app import smoke, and no behavior movement in PR1.
- `server/tests/test_device_operations_router_facade.py`
  - Proves old imports and new domain imports resolve to the same module objects during the migration.
- `server/tests/test_device_operations_pairing.py`
  - Characterizes pair request, admin approval/rejection, websocket pair events, and pair status behavior.
- `server/tests/test_device_operations_polling_reporting.py`
  - Covers device task polling, progress/report heartbeat paths, and task response shape.
- `server/tests/test_device_operations_status_lifecycle.py`
  - Covers offline checker lifecycle behavior: `pair_ws_manager.drain_heartbeats()`, DB heartbeat flush/requeue on failure, offline device marking, admin offline broadcast, stuck task cancel/fail/reset behavior, channel item reset through existing services, and app lifespan start/stop of the checker task.
- `server/tests/test_device_operations_uploads.py`
  - Covers script upload/download, templates, selectors, avatars, and asset upload response compatibility.
- `server/tests/test_device_operations_content_bridge.py`
  - Locks the temporary content/collection/DM bridge behavior before `content_collection` assumes business ownership.

### Existing Tests To Keep Green

- `server/tests/test_device_api.py`
- `server/tests/test_device_endpoints.py`
- `server/tests/test_devices_api.py`
- `server/tests/test_device_service.py`
- `server/tests/test_tasks_api.py`
- `server/tests/test_task_service.py`
- `server/tests/test_content_api.py`
- `server/tests/test_collection_builder.py`
- `server/tests/test_dm_sequences_api.py`

## PR Sequence

### PR1: Boundary And Auth Characterization

- [ ] Add `test_device_operations_auth_parity.py` with route and websocket snapshots for `/api/device/*` and `/api/devices/*`.
- [ ] Add `test_device_operations_domain_boundary.py` with expected red tests for the missing package and README.
- [ ] Add `test_device_operations_status_lifecycle.py` characterization tests for `server/app/main.py::_offline_checker` and app lifespan start/stop without moving lifecycle code yet.
- [ ] Record route dependencies by callable name, including `get_db`, `verify_device_secret`, `verify_admin_token`, and role dependencies used by `/api/devices`.
- [ ] Verify no production code changes.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_status_lifecycle.py -q
```

Expected before PR2: auth and lifecycle characterization passes; package/README tests fail because the domain package does not exist yet.

### PR2: Domain Skeleton And Facade Register

- [ ] Create `server/app/domains/device_operations/__init__.py`.
- [ ] Create `server/app/domains/device_operations/README.md`.
- [ ] Document the facade register for `app.routers.device` and `app.routers.devices`.
- [ ] Keep route behavior in the legacy router files.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_status_lifecycle.py -q
```

Expected after PR2: auth parity, lifecycle characterization, domain metadata, README, and app import smoke pass.

### PR3: Router Compatibility Move

- [ ] Copy current `server/app/routers/device.py` behavior into `server/app/domains/device_operations/device_router.py`.
- [ ] Copy current `server/app/routers/devices.py` behavior into `server/app/domains/device_operations/admin_router.py`.
- [ ] Replace legacy router files with module aliases that preserve module identity during the migration.
- [ ] Add `test_device_operations_router_facade.py`.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_router_facade.py server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py -q
```

Expected after PR3: old imports and domain imports point to the same module objects, and existing device API tests pass.

### PR4: Pairing, Status, Polling, And Reporting Split

- [ ] Move pair request/status/admin approve/reject logic to `pairing.py`.
- [ ] Move status websocket lifecycle and offline/heartbeat boundaries to `status_ws.py`.
- [ ] Move task poll response assembly to `polling.py`.
- [ ] Move progress/report/stats/heartbeat/risk report handlers to `reporting.py`.
- [ ] Keep router functions thin and route paths unchanged.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_pairing.py server/tests/test_device_operations_polling_reporting.py server/tests/test_device_api.py server/tests/test_devices_api.py -q
```

### PR5: Offline Checker And Lifespan Split

- [ ] Move `server/app/main.py::_offline_checker` behavior into `status_lifecycle.py` behind a small app-lifespan adapter.
- [ ] Preserve `pair_ws_manager.drain_heartbeats()` semantics and assert drained heartbeats are flushed to the DB.
- [ ] Preserve DB heartbeat flush requeue-on-failure behavior so failed writes are not silently dropped.
- [ ] Preserve offline device marking and `pair_ws_manager.broadcast_to_admins` offline notifications.
- [ ] Preserve `TASK_STALE_MINUTES` stuck task handling, including cancel/fail/reset behavior and channel item reset through existing services.
- [ ] Preserve app lifespan start/stop behavior so the checker task starts once and is cancelled/awaited cleanly on shutdown.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_status_lifecycle.py server/tests/test_device_operations_pairing.py server/tests/test_devices_api.py server/tests/test_tasks_api.py -q
```

### PR6: Script Assets And Content Bridge Split

- [ ] Move selectors, prompt templates, script version/download/upload, calibration, and AI proxy boundaries to `script_assets.py`.
- [ ] Move content generation, collection reports, comment claim/release, DM claim/send/release, comment AI reply, user profile, and avatar handlers to `content_bridge.py`.
- [ ] Keep the bridge explicit: device auth and route response shaping live here; long-term collection business ownership is deferred to `content_collection`.
- [ ] Add bridge tests that assert old `/api/device/*` response shapes.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_uploads.py server/tests/test_device_operations_content_bridge.py server/tests/test_content_api.py server/tests/test_collection_builder.py server/tests/test_dm_sequences_api.py -q
```

### PR7: Facade Cleanup Gates

- [ ] Inventory imports of `app.routers.device` and `app.routers.devices`.
- [ ] Move application wiring to domain imports only after facade tests prove no legacy behavior drift.
- [ ] Keep legacy modules as compatibility shims until a separate cleanup commit removes them with a failing-then-passing test.
- [ ] Update `server/app/domains/device_operations/README.md` with completed gate status.

Run:

```powershell
rg -n "app\.routers\.(device|devices)|from app\.routers import (device|devices)" server/app server/tests
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_router_facade.py server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py -q
```

## Boundary And Compatibility Tests

- Route snapshot tests must enumerate every method/path under `/api/device`, `/api/devices`, `/api/device/ws/pair/{token}`, `/api/device/ws/status`, and `/api/devices/ws/pair-events`.
- Auth tests must distinguish device-secret routes from admin-token routes and websocket-specific auth behavior.
- Response-shape tests must cover at least poll, report, collect-report, DM claim, DM release, script upload/download, avatar upload, and admin pair approve/reject.
- Lifecycle tests must cover `pair_ws_manager.drain_heartbeats()`, DB heartbeat flush and requeue on write failure, device offline marking, admin offline broadcasts, `TASK_STALE_MINUTES` stuck task cancel/fail/reset behavior, channel item reset through existing services, and app lifespan start/stop of the checker task.
- Facade tests must prove `importlib.import_module("app.routers.device") is importlib.import_module("app.domains.device_operations.device_router")` during the alias phase.
- Facade tests must prove `importlib.import_module("app.routers.devices") is importlib.import_module("app.domains.device_operations.admin_router")` during the alias phase.
- App import smoke must continue loading `app.main.app` without duplicate route registration.
- Existing tests listed in the file map are part of the compatibility contract and must pass in the PR that touches their behavior.

## Facade Cleanup Gates

- [ ] `server/app/domains/device_operations/README.md` lists every active facade, target module, introduction PR, owner, and exit condition.
- [ ] No cleanup PR may remove `app.routers.device` or `app.routers.devices` while any production import still references them.
- [ ] Old import paths remain tested until the cleanup commit that removes them.
- [ ] Cleanup must not change public route paths, methods, auth dependencies, websocket paths, or response shapes.
- [ ] Content/collection/DM bridge cleanup waits for the `content_collection` domain plan to land and provide adapter tests.
- [ ] The final cleanup PR must include `rg` evidence showing only expected compatibility tests mention legacy router paths.

## Final Verification

Run from the repository root after the final PR in this child plan:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_router_facade.py server/tests/test_device_operations_pairing.py server/tests/test_device_operations_polling_reporting.py server/tests/test_device_operations_status_lifecycle.py server/tests/test_device_operations_uploads.py server/tests/test_device_operations_content_bridge.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py server/tests/test_device_service.py server/tests/test_tasks_api.py server/tests/test_task_service.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_api.py server/tests/test_collection_builder.py server/tests/test_dm_sequences_api.py -q
rg -n "app\.routers\.(device|devices)|from app\.routers import (device|devices)" server/app server/tests
```

Expected:

- All new device operations tests pass.
- Existing device, devices, task, content, collection, and DM smoke tests pass.
- `rg` output contains only approved compatibility shims or tests until the explicit cleanup PR removes the shims.
- No `ai_video_series` source file is modified by this child domain implementation.

## GSTACK REVIEW REPORT

Status: PLANNED.
Date: 2026-06-18.
Scope: child implementation plan only; no device operations code is implemented by this document.

| Review | Status | Notes |
|---|---|---|
| CEO Review | INHERITED | Parent plan approved deferring device operations as an independent child domain instead of merging it into the `ai_video_series` PR chain. |
| Eng Review | REQUIRED BEFORE CODING | Future implementer should run engineering review after PR1 snapshots expose the real route/auth surface. |
| Design Review | SKIPPED | No UI or product screen changes are planned. |
| DX Review | LIGHTWEIGHT | Plan includes file map, tests, PR sequence, cleanup gates, and commands so an agent can execute without inventing migration phases. |
| Codex Review | OPTIONAL | Recommended before facade cleanup because websocket and device-secret auth behavior are easy to regress. |

Decision: proceed only after `ai_video_series` facade migration is proven. This plan preserves the approved broad modularization scheme while keeping device operations outside the `ai_video_series` implementation chain.
