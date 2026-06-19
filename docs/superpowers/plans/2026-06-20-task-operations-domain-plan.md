# Task Operations Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move admin task creation, listing, cancellation, deletion, batch creation, parameter normalization, and task websocket notifications out of the flat `server/app/routers/tasks.py` router into `app.domains.task_operations`.

**Architecture:** Keep public `/api/tasks/*` behavior stable. Start with route/auth, response-shape, and notification characterization. Then add a metadata-only domain skeleton, move the router behind compatibility facades, split task read models and admin mutation use cases, and finally wire `app.main` to domain imports. Device task polling/reporting remains in `device_operations`; chain instance orchestration remains in `account_operations`; content template and DM sequence business logic remains in `content_collection` and is used through adapters.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pytest, existing `task_service`, `content_service`, `channel_service`, `device_operations`, `content_collection`, and `account_operations`.

---

## First Tasks

- [ ] Characterize `/api/tasks/*` route methods, endpoint ownership, and auth dependencies.
- [ ] Characterize task creation/list/detail/batch/cancel/delete response shapes.
- [ ] Characterize websocket notifications for `new_task_available`, `task_updated`, `tasks_changed`, and `cancel_task`.
- [ ] Create `server/app/domains/task_operations`.
- [ ] Move `app.routers.tasks` behind a compatibility alias.
- [ ] Split task parameter resolution, admin use cases, read models, realtime events, and adapters.

## File Map

### New Domain Files

- `server/app/domains/task_operations/__init__.py`
  - Exports `DOMAIN_NAME = "task_operations"` and `PUBLIC_ROUTE_PREFIX = "/api/tasks"`.
- `server/app/domains/task_operations/README.md`
  - Facade register, route/auth snapshots, ownership boundaries, notification payloads, and cleanup gates.
- `server/app/domains/task_operations/tasks_router.py`
  - Owns `/api/tasks/*` route assembly after the compatibility move.
- `server/app/domains/task_operations/schemas.py`
  - Owns request models currently embedded in `tasks.py`: task create, batch create, and batch delete.
- `server/app/domains/task_operations/read_models.py`
  - Owns task list/detail response helpers and direct Pydantic task payload pass-through conventions.
- `server/app/domains/task_operations/param_resolution.py`
  - Owns task parameter validation and normalization, content template resolution, DM sequence fallback resolution, nurture keyword expansion, and nurture subtask template resolution.
- `server/app/domains/task_operations/task_use_cases.py`
  - Owns admin task create, batch create, list, get, cancel, batch delete, and delete orchestration.
- `server/app/domains/task_operations/realtime_events.py`
  - Owns websocket notification helpers for `new_task_available`, `task_updated`, `tasks_changed`, and direct device `cancel_task`.
- `server/app/domains/task_operations/adapters.py`
  - Narrow adapter layer over `task_service`, `content_service`, `channel_service`, ORM lookups, and `pair_ws_manager`.

### Compatibility Facades To Modify In Future PRs

- `server/app/routers/tasks.py`
  - Becomes a compatibility alias to `app.domains.task_operations.tasks_router`.
- `server/app/main.py`
  - Keeps public route registration stable while imports migrate.

### Explicit Non-Ownership

- `server/app/domains/device_operations/polling.py`
  - Continues to own device task polling and channel item leasing.
- `server/app/domains/device_operations/reporting.py`
  - Continues to own device task progress/result reporting and heartbeat/risk reporting.
- `server/app/domains/account_operations/chain_use_cases.py`
  - Continues to own chain instance task orchestration and step retry/cancel semantics.
- `server/app/domains/content_collection`
  - Continues to own content template, collection, and DM sequence business use cases. `task_operations` may call through adapters, but must not absorb content/DM ownership.

### New Tests

- `server/tests/test_task_operations_auth_parity.py`
  - Snapshots `/api/tasks/*` route methods, endpoint module, endpoint names, and auth dependencies.
- `server/tests/test_task_operations_domain_boundary.py`
  - Verifies the future contract is documented, PR1 has not moved behavior, `tasks.py` remains outside device/account/content domains, and app import smoke keeps task routes registered once.
- `server/tests/test_task_operations_read_models.py`
  - Covers current task create/list/detail/batch response shapes.
- `server/tests/test_task_operations_notifications.py`
  - Patches/asserts `pair_ws_manager.broadcast_to_devices`, `broadcast_to_admins`, and `send_to_device` around current task mutation routes.
- `server/tests/test_task_operations_router_facade.py`
  - Proves legacy `app.routers.tasks` and new domain router imports resolve to the same module object during migration.
- `server/tests/test_task_operations_mutations.py`
  - Covers create, batch create, batch delete, cancel, delete, and parameter resolution use cases after extraction.

### Existing Tests To Keep Green

- `server/tests/test_tasks_api.py`
- `server/tests/test_task_service.py`
- `server/tests/test_device_api.py`
- `server/tests/test_device_endpoints.py`
- `server/tests/test_account_operations_chain_orchestration.py`
- `server/tests/test_content_collection_device_bridge.py`
- `server/tests/test_content_collection_mutations.py`

## PR Sequence

### PR1: Route/Auth, Response, And Notification Characterization

- [ ] Add route/auth snapshots for all `/api/tasks/*` routes.
- [ ] Add response-shape tests for single create, list, detail, direct batch create, batch delete, cancel, and delete.
- [ ] Add notification characterization for `new_task_available`, `task_updated`, `tasks_changed`, and direct device `cancel_task`.
- [ ] Confirm device polling/reporting remains in `device_operations` and chain orchestration remains in `account_operations`.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_auth_parity.py server/tests/test_task_operations_domain_boundary.py server/tests/test_task_operations_read_models.py server/tests/test_task_operations_notifications.py -q
```

Expected before PR2: route/auth characterization, response shapes, and notification tests pass; domain metadata tests prove the future contract is documented and the package has not been created yet.

### PR2: Domain Skeleton And Facade Register

- [ ] Create `server/app/domains/task_operations/__init__.py`.
- [ ] Create `server/app/domains/task_operations/README.md`.
- [ ] Document task ownership boundaries, explicit exclusions, notification payloads, and cleanup gates.
- [ ] Keep route behavior in `server/app/routers/tasks.py`.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_auth_parity.py server/tests/test_task_operations_domain_boundary.py -q
```

Expected after PR2: auth parity, domain metadata, README, and app import smoke pass.

### PR3: Route Module Compatibility Move

- [ ] Move current `tasks.py` behavior to `tasks_router.py`.
- [ ] Replace legacy `server/app/routers/tasks.py` with a compatibility alias.
- [ ] Keep route paths, methods, dependencies, response shapes, and notification payloads unchanged.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_router_facade.py server/tests/test_task_operations_auth_parity.py server/tests/test_tasks_api.py -q
```

### PR4: Param Resolution And Admin Task Use Cases

- [ ] Move request schemas to `schemas.py`.
- [ ] Move parameter validation and resolution helpers to `param_resolution.py`.
- [ ] Move task create/list/detail/batch/cancel/delete orchestration to `task_use_cases.py`.
- [ ] Move task websocket helper calls to `realtime_events.py`.
- [ ] Keep `tasks_router.py` as the FastAPI dependency and HTTP error mapping boundary.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_read_models.py server/tests/test_task_operations_mutations.py server/tests/test_task_operations_notifications.py server/tests/test_tasks_api.py server/tests/test_task_service.py -q
```

### PR5: App Wiring And Cleanup Gates

- [ ] Inventory production imports of `app.routers.tasks`.
- [ ] Move `server/app/main.py` route wiring to `app.domains.task_operations.tasks_router`.
- [ ] Keep the legacy router module until cleanup tests prove no old production callers remain.
- [ ] Update README cleanup gate status.

Run:

```powershell
rg -n "app\.routers\.tasks|from app\.routers import tasks|include_router\(tasks\.router" server/app server/tests
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_auth_parity.py server/tests/test_task_operations_router_facade.py server/tests/test_task_operations_read_models.py server/tests/test_task_operations_notifications.py server/tests/test_tasks_api.py server/tests/test_task_service.py -q
```

## Boundary And Compatibility Tests

- Route snapshot tests must cover every method/path under `/api/tasks`.
- Auth tests must capture the current `verify_admin_token` dependency for every task admin route.
- Response-shape tests must assert current Pydantic task payload keys and direct/batch mutation summary payloads.
- Notification tests must patch/assert:
  - `broadcast_to_devices({"event": "new_task_available"})`
  - `broadcast_to_admins({"event": "task_updated", ...})`
  - `broadcast_to_admins({"event": "tasks_changed"})`
  - `send_to_device(device_id, {"event": "cancel_task", "task_id": ...})`
- Facade tests must prove `app.routers.tasks` is the same module object as `app.domains.task_operations.tasks_router` during the alias phase.
- Device polling/reporting tests must continue to prove device-owned task leasing and result reporting remain outside task operations.
- Account operations chain orchestration tests must continue to prove chain retry/cancel ownership remains outside task operations.

## Facade Cleanup Gates

- [ ] `server/app/domains/task_operations/README.md` lists every active facade, target module, introduction PR, owner, and exit condition.
- [ ] No cleanup PR may remove `server/app/routers/tasks.py` while production imports still reference it.
- [ ] `device_operations` polling/reporting route snapshots must still point to device-owned modules.
- [ ] `account_operations` chain orchestration tests must still pass.
- [ ] `content_collection` content/DM tests must still pass.
- [ ] Cleanup must not change public route paths, methods, auth dependencies, response shapes, task statuses, or websocket payloads.
- [ ] Final cleanup must include `rg` evidence showing only approved compatibility tests mention legacy task router paths.

## Final Verification

Run from the repository root after the final PR in this child plan:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_auth_parity.py server/tests/test_task_operations_domain_boundary.py server/tests/test_task_operations_router_facade.py server/tests/test_task_operations_read_models.py server/tests/test_task_operations_mutations.py server/tests/test_task_operations_notifications.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_tasks_api.py server/tests/test_task_service.py server/tests/test_device_api.py server/tests/test_device_endpoints.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_chain_orchestration.py server/tests/test_content_collection_device_bridge.py server/tests/test_content_collection_mutations.py -q
rg -n "app\.routers\.tasks|from app\.routers import tasks|include_router\(tasks\.router" server/app server/tests
rg -n "new_task_available|task_updated|tasks_changed|cancel_task|pair_ws_manager\.(broadcast_to_admins|broadcast_to_devices|send_to_device)" server/app/domains/task_operations server/tests/test_task_operations_notifications.py
```

Expected:

- All new task operations tests pass.
- Existing task, device, account-chain, and content/DM tests pass.
- Notification tests prove current event names and payload shapes are unchanged.
- `rg` output contains only approved compatibility shims, README entries, or tests until the explicit cleanup PR removes the shim.
- No `device_operations`, `account_operations`, `content_collection`, or `ai_video_series` source file changes unless a PR explicitly updates documented adapter boundaries.

## GSTACK REVIEW REPORT

Status: PLANNED.
Date: 2026-06-20.
Scope: child implementation plan only; no task operations code is implemented by this document.

| Review | Status | Notes |
|---|---|---|
| CEO Review | INHERITED | Parent modularization strategy approves child plans for independent domains. |
| Eng Review | REQUIRED BEFORE DEEP CODING | PR1 snapshots must clarify task/content/device/account boundaries before use-case extraction. |
| Design Review | SKIPPED | No UI or product screen changes are planned. |
| DX Review | LIGHTWEIGHT | Plan includes executable PR phases, route surfaces, notification payloads, test files, and cleanup gates. |
| Codex Review | OPTIONAL | Recommended before PR4 because parameter resolution crosses content and DM adapters. |

Decision: proceed after PR1 characterization. This domain is a standalone follow-up because task administration is a shared boundary between device operations, content collection, and account operations.
