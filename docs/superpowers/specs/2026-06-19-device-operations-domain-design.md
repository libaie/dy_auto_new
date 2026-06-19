# Device Operations Domain PR1 Design

Status: approved for specification.
Date: 2026-06-19.
Scope: backend server structure, boundary tests, and migration design only.

## Context

The server still has a flat router-heavy structure. `ai_video_series` has already proven the domain migration playbook: create behavior-neutral characterization tests, introduce a domain package, preserve old import paths through compatibility facades, split business logic into focused modules, and add explicit cleanup gates.

The next largest and riskiest router is `server/app/routers/device.py`. It is roughly 66 KB and mixes several responsibilities:

- device pairing and pair websocket behavior
- device status websocket and heartbeat behavior
- task polling and progress/report updates
- device registration and admin device management handoff
- selector, prompt-template, script download/upload, and calibration endpoints
- AI proxy, generated content, collection reports, comment/user/avatar reports, and DM claim/report/release bridge behavior

`server/app/routers/devices.py` is the related admin surface for device records, pair events, pair approval/rejection, disconnect/delete, and direct device notifications. `server/app/main.py::_offline_checker` also belongs to the device operations boundary because it drains websocket heartbeats, updates the DB, marks stale devices offline, broadcasts offline status to admins, and handles stuck tasks.

The current worktree contains many unrelated staged and unstaged changes. PR1 must be limited to boundary tests and documentation so it can be reviewed independently and does not absorb unrelated production, content, or account work.

## Goal

Create a behavior-neutral PR1 for the `device_operations` domain. The PR should prove what the current device surface does before any production code is moved.

The design outcome is a stable contract for future migration PRs:

- all public device/admin-device routes remain unchanged
- websocket paths remain unchanged
- device-secret and admin-token authorization boundaries remain unchanged
- offline checker and heartbeat lifecycle behavior is characterized before moving it
- content and DM bridge behavior is identified as a temporary bridge, not final ownership
- legacy router imports stay in place until future compatibility facades are introduced and tested

## Non-Goals

PR1 must not:

- move `server/app/routers/device.py`
- move `server/app/routers/devices.py`
- edit `server/app/main.py::_offline_checker`
- create the production `app.domains.device_operations` package as active code
- change route paths, methods, dependencies, response shapes, websocket behavior, or background task behavior
- move content, data, DM, account, channel, chain, or video production ownership
- clean up old imports
- modify frontend code

## Recommended Approach

Use the same incremental migration strategy that worked for `ai_video_series`, but start with a smaller, safer PR1:

1. Add route/auth/websocket characterization tests for `/api/device/*` and `/api/devices/*`.
2. Add lifecycle characterization tests for `_offline_checker` and app lifespan task management.
3. Add domain-boundary tests that document the expected future package and README, without requiring behavior movement.
4. Add a short domain README or spec reference if needed, but keep executable production code untouched.

This is preferable to moving `device.py` immediately because the file combines transport, websocket state, DB writes, content bridge behavior, and task orchestration. Without characterization tests, a mechanical move would be hard to distinguish from behavior drift.

## Architecture Boundary

Future domain target:

```text
app.domains.device_operations
  __init__.py               domain metadata
  README.md                 facade register and cleanup gates
  device_router.py          /api/device route assembly
  admin_router.py           /api/devices route assembly
  pairing.py                pair request/status/admin approval/rejection
  status_ws.py              device status websocket connection lifecycle
  status_lifecycle.py       offline checker and heartbeat flush lifecycle
  polling.py                task polling and lease response shaping
  reporting.py              progress/report/stats/heartbeat/risk reports
  script_assets.py          selectors, templates, script download/upload, calibration
  content_bridge.py         temporary bridge to content/collection/DM use cases
  adapters.py               narrow wrappers over existing services
```

PR1 does not create all of these modules. It only writes tests and documentation that make this boundary explicit.

## Route And Auth Characterization

PR1 should add a route snapshot test that enumerates every `APIRoute` and websocket path under:

- `/api/device`
- `/api/devices`

For each HTTP route, capture:

- path
- methods
- route name
- dependency callable identities

For websocket routes, capture:

- path
- endpoint name
- whether the websocket is device-facing or admin-facing

The auth snapshot must distinguish:

- device-secret routes
- admin-token routes
- role-gated routes, if any
- websocket-specific auth or token handling

The snapshot should be explicit and reviewed as a contract. When later PRs move routers into `app.domains.device_operations`, the same snapshot must still pass.

## Lifecycle Characterization

`server/app/main.py::_offline_checker` is part of this domain boundary even though it currently lives in `main.py`.

PR1 should add lifecycle tests that characterize:

- `pair_ws_manager.drain_heartbeats()` is called
- drained heartbeats are flushed to the DB
- heartbeat flush failures requeue heartbeats rather than dropping them
- stale devices are marked offline
- admin offline broadcasts preserve the current event payload shape
- `TASK_STALE_MINUTES` drives stuck task detection
- stuck tasks are cancelled, failed, or reset with existing behavior
- related channel item reset behavior remains covered through existing service boundaries
- app lifespan starts the checker task once and cancels/awaits it on shutdown

If any part of the checker is too hard to test directly without changing production code, PR1 should add the narrowest characterization possible and document the remaining gap in the test file. It should not refactor `_offline_checker` yet.

## Domain Boundary Tests

PR1 should include tests that describe the future domain package without moving behavior:

- `app.domains.device_operations` will expose `DOMAIN_NAME = "device_operations"`.
- It will expose public route prefixes `("/api/device", "/api/devices")`.
- Its README will document facade registers for `app.routers.device` and `app.routers.devices`.
- It will document that content/collection/DM behavior remains a bridge until `content_collection` owns those use cases.

The tests should be structured so the package/README expectations can be red before skeleton creation and green once PR2 creates the skeleton. Route/auth characterization tests should pass in PR1 because they describe the current application.

## Data Flow Contracts

Device task polling:

```text
device client -> /api/device/poll -> device auth -> task lease/response shaping -> device response
```

Device reporting:

```text
device client -> /api/device/progress or /api/device/report -> device auth -> task/device/content side effects -> admin/device websocket notifications when currently emitted
```

Device status websocket:

```text
device websocket -> pair_ws_manager status connection -> heartbeat records -> offline checker -> DB status + admin broadcast
```

Admin device management:

```text
admin client -> /api/devices/* -> admin auth -> device record/pair request mutation -> pair_ws_manager notify/broadcast
```

Content and DM bridge:

```text
device client -> /api/device/content-or-dm endpoint -> device auth -> existing content/data/DM services -> current realtime events
```

PR1 should not change these flows. It should only capture enough of them to make later movement safe.

## Error Handling Contracts

The tests should preserve current error behavior for representative paths:

- missing or invalid device identity
- missing or invalid admin authorization
- invalid pair token or missing pair request
- stale/offline device behavior
- no task available polling behavior
- report/progress payload validation failures

PR1 does not need exhaustive endpoint-level assertions for every route. It must capture the high-risk boundaries that would regress during a move: auth, websocket path, response shape, lifecycle side effects, and realtime notifications.

## Testing Strategy

Expected new tests:

- `server/tests/test_device_operations_auth_parity.py`
  - route/method/dependency snapshots for `/api/device/*` and `/api/devices/*`
  - websocket path snapshot for pair/status/admin pair events
- `server/tests/test_device_operations_domain_boundary.py`
  - future domain metadata and README expectations
  - app import smoke
  - no behavior movement in PR1
- `server/tests/test_device_operations_status_lifecycle.py`
  - offline checker heartbeat drain/flush/requeue behavior
  - stale-device offline marking and admin broadcast behavior
  - stuck task handling characterization
  - lifespan task start/stop characterization where feasible

Focused verification command:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_status_lifecycle.py -q
```

Existing compatibility checks to keep green when relevant:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py -q
```

If current dirty-tree changes make the full compatibility set fail, PR1 should also be validated in a clean worktree at the PR1 commit.

## Compatibility And Cleanup Gates

PR1 does not add a compatibility alias yet. The future cleanup gates are:

- do not replace `app.routers.device` until a domain router has identical route/auth snapshots
- do not replace `app.routers.devices` until admin device and pair-event websocket behavior is snapshotted
- do not move `_offline_checker` until lifecycle tests cover heartbeat drain, DB flush, requeue, offline broadcast, stuck task handling, and lifespan behavior
- do not move content/collection/DM bridge ownership until `content_collection` has its own tests and adapter plan
- do not remove legacy imports until `rg` proves only compatibility shims/tests still reference them

## Risks

- Websocket behavior can regress without obvious HTTP test failures.
- `_offline_checker` mixes websocket manager state, DB writes, and task recovery.
- Device endpoints act as a bridge into content, DM, account, and task domains.
- The current worktree is very dirty, so unrelated tests may fail for reasons outside PR1.
- Snapshot tests can become brittle if they overfit implementation details instead of public contracts.

Mitigation:

- snapshot route paths, methods, and dependency identities, not incidental local variables
- isolate lifecycle tests around observable side effects
- keep PR1 behavior-neutral
- validate in a clean worktree before claiming the PR1 contract is stable

## Success Criteria

PR1 is complete when:

- route/auth/websocket snapshots exist for device and admin-device surfaces
- lifecycle characterization exists for the offline checker boundary
- future `device_operations` ownership is documented
- no production behavior is moved
- focused tests run and produce understood results
- any expected red tests are explicitly tied to future skeleton creation
- no unrelated dirty-tree files are committed

## Implementation Planning Defaults

- PR1 should stay green. Do not add expected-red tests for a missing `device_operations` package unless the same PR also creates the minimal metadata/README skeleton needed to make those tests pass.
- Route snapshots should include all dependency callable identities for device/admin-device routes. The implementation plan may add helper names for role closures, mirroring the `ai_video_series` route-auth test pattern.
- Lifecycle characterization should start with direct `_offline_checker` and lifespan-boundary tests using monkeypatches around `pair_ws_manager`, `SessionLocal`, sleep timing, and task creation. If a behavior cannot be isolated without production refactoring, the test must cover the closest observable side effect and name the remaining gap.
- PR1 should not extract helper functions from `_offline_checker`. Extraction belongs to a later movement PR after characterization exists.

These defaults keep PR1 behavior-neutral while giving the implementation plan enough precision to avoid inventing scope.
