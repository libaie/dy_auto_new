# Device Operations Domain

This domain will own device pairing, device status websockets, task polling,
device reporting, script assets, and the admin device management surface.

## PR2 Allowed

- Create `server/app/domains/device_operations/__init__.py`.
- Create this README.
- Expose `DOMAIN_NAME = "device_operations"`.
- Expose `PUBLIC_ROUTE_PREFIXES = ("/api/device", "/api/devices")`.
- Document the facade register and cleanup gates.

## PR2 Not Allowed

- Do not move route behavior in PR2.
- Do not create `device_router.py` or `admin_router.py` in PR2.
- Do not move `server/app/main.py::_offline_checker` in PR2.
- Do not change `/api/device/*` or `/api/devices/*` paths, methods, auth dependencies, websocket paths, or response shapes.
- Do not move content, collection, DM, account, channel, chain, or video production ownership in PR2.
- Do not modify frontend code.

## PR3 Allowed

- Create `device_router.py` from the current `app.routers.device` behavior.
- Create `admin_router.py` from the current `app.routers.devices` behavior.
- Replace legacy router files with compatibility facades.
- Keep route paths, methods, dependencies, websocket paths, and response shapes unchanged.

## PR3 Not Allowed

- Do not split handler internals yet.
- Do not move `server/app/main.py::_offline_checker` yet.
- Do not change application wiring away from legacy imports yet.
- Do not move content, collection, DM, account, channel, chain, or video production ownership yet.

## PR4a Allowed

- Move device pairing routes to `pairing.py`.
- Move the device status websocket and pending-task notification helper to `status_ws.py`.
- Keep `device_router.py` as the `/api/device/*` route aggregator.
- Keep all public paths, methods, auth dependencies, websocket paths, and response shapes unchanged.

## PR4a Not Allowed

- Do not move task polling, progress/reporting, script assets, content bridge, DM bridge, or avatar handlers yet.
- Do not move `server/app/main.py::_offline_checker` yet.
- Do not change admin device management routes yet.

## PR4b Allowed

- Move `/poll` task leasing and response shaping to `polling.py`.
- Move `/progress`, `/report`, `/stats/increment`, `/heartbeat`, and `/risk-report` to `reporting.py`.
- Keep `device_router.py` as the `/api/device/*` route aggregator.
- Keep route order, public paths, methods, auth dependencies, and response shapes unchanged.

## PR4b Not Allowed

- Do not move device registration, script assets, calibration, AI proxy, content bridge, DM bridge, user profile, or avatar handlers yet.
- Do not move `server/app/main.py::_offline_checker` yet.
- Do not change admin device management routes yet.

## PR4c Allowed

- Move selector sync, prompt-template sync, script version/download/upload, template image sync, and calibration routes to `script_assets.py`.
- Keep `device_router.py` as the `/api/device/*` route aggregator.
- Keep route order, public paths, methods, auth dependencies, and response shapes unchanged.

## PR4c Not Allowed

- Do not move device registration, AI proxy, content bridge, DM bridge, user profile, or avatar handlers yet.
- Do not move `server/app/main.py::_offline_checker` yet.
- Do not change admin device management routes yet.

## PR4d Allowed

- Move comment claim/release, generated content, AI proxy, collection reports, DM claim/report/release, comment AI reply, user profile, and avatar routes to `content_bridge.py`.
- Keep `device_router.py` as the `/api/device/*` route aggregator.
- Keep route order, public paths, methods, auth dependencies, and response shapes unchanged.
- Keep this module explicitly documented as a temporary bridge until `content_collection` owns the business use cases.

## PR4d Not Allowed

- Do not move device registration yet.
- Do not move `server/app/main.py::_offline_checker` yet.
- Do not change admin device management routes yet.
- Do not claim final ownership of content, collection, DM, or user profile business logic.

## PR5 Allowed

- Move `_offline_checker` behavior to `status_lifecycle.py`.
- Keep `app.main._offline_checker` as a thin lifespan-compatible wrapper.
- Preserve heartbeat drain, DB flush, requeue, offline broadcasts, stuck-task cancel/fail handling, and channel item reset behavior.

## PR5 Not Allowed

- Do not change lifespan task start/cancel behavior.
- Do not change heartbeat timeout windows, `TASK_STALE_MINUTES`, websocket payload shapes, or task recovery semantics.
- Do not change admin device management routes.

## PR6 Allowed

- Add route ownership and response-shape tests for `script_assets.py`.
- Add route ownership and response-shape tests for `content_bridge.py`.
- Keep all `/api/device/*` public paths, methods, auth dependencies, and response shapes unchanged.
- Keep `content_bridge.py` explicitly documented as a temporary bridge until `content_collection` owns those business use cases.

## PR6 Not Allowed

- Do not remove `app.routers.device` or `app.routers.devices` compatibility facades.
- Do not move content, collection, DM, or user profile business ownership out of the temporary bridge yet.
- Do not change application wiring away from legacy router imports yet.

## PR7 Allowed

- Inventory production imports of `app.routers.device` and `app.routers.devices`.
- Move `server/app/main.py` route wiring to `app.domains.device_operations.device_router` and `app.domains.device_operations.admin_router`.
- Keep `app.routers.device` and `app.routers.devices` as compatibility facades for old import paths.
- Keep all public paths, methods, auth dependencies, websocket paths, and response shapes unchanged.

## PR7 Not Allowed

- Do not delete `server/app/routers/device.py` or `server/app/routers/devices.py`.
- Do not remove router facade tests yet.
- Do not change device, admin device, websocket, script asset, or content bridge behavior.

## Ownership Rules

- `app.domains.device_operations` owns the target migration boundary for `/api/device/*` and `/api/devices/*`.
- `app.routers.device` remains the compatibility import path for `/api/device/*` callers outside app wiring.
- `app.routers.devices` remains the compatibility import path for `/api/devices/*` callers outside app wiring.
- `app.domains.device_operations.pairing` owns device pair request/status and pair-status websocket behavior.
- `app.domains.device_operations.status_ws` owns the device status websocket and pending-task websocket notification helper.
- `app.domains.device_operations.polling` owns device task polling, cancellation delivery, DM sequence sync, and poll response shaping.
- `app.domains.device_operations.reporting` owns task progress, task result, stats increment, heartbeat, and risk-control reporting.
- `app.domains.device_operations.script_assets` owns selectors, prompt-template sync, script packages, template images, and calibration uploads.
- `app.domains.device_operations.content_bridge` temporarily owns device-authenticated bridges for content generation, AI proxy, collection reports, comment replies, DM flows, user profiles, and avatars.
- `app.domains.device_operations.status_lifecycle` owns heartbeat flush, stale-device offline marking, stuck-task handling, and channel item reset behavior.
- `app.domains.device_operations.device_service` owns `DeviceService` registration, heartbeat, status lookup, and offline marking.
- `server/app/main.py::_offline_checker` remains as a thin lifespan-compatible wrapper around `status_lifecycle.offline_checker`.
- Content, collection, and DM endpoints under `/api/device/*` are a temporary bridge; final business ownership belongs to a future `content_collection` domain.
- Domain non-router modules must avoid FastAPI imports unless they are route assembly modules.

## Facade Register

| Facade | Target | Introduced | Exit condition |
|---|---|---|---|
| `app.routers.device` | `app.domains.device_operations.device_router` | PR3 | Route/auth/websocket snapshots pass with the domain router and all callers have an explicit compatibility path. |
| `app.routers.devices` | `app.domains.device_operations.admin_router` | PR3 | Admin device route and pair-event websocket snapshots pass with the domain router and all callers have an explicit compatibility path. |
| `app.main._offline_checker` | `app.domains.device_operations.status_lifecycle` | PR5 | Lifecycle tests cover heartbeat drain, DB flush, requeue, offline broadcast, stuck task handling, and lifespan start/stop through the domain entrypoint. |
| `/api/device/*` content and DM bridge handlers | Future `content_collection` domain adapters | Deferred | `content_collection` owns those business use cases and adapter tests prove unchanged device response shapes. |
| `app.services.device_service` | `app.domains.device_operations.device_service` | Device service domain slice | Remove only after `rg -n "app\.services\.device_service" server/app -g "*.py"` returns no production imports and remaining legacy-path tests are migrated or retired. |

## Migration Checklist

1. Characterize current route/auth/websocket and offline lifecycle behavior.
2. Add this metadata-only domain skeleton.
3. Move legacy router behavior behind `device_router.py` and `admin_router.py` with compatibility facades.
4. Split pairing, status websocket, polling, reporting, script assets, and bridge behavior into focused modules.
5. Move the offline checker into `status_lifecycle.py` after lifecycle tests cover the behavior.
6. Lock script asset and content bridge response shapes with dedicated tests.
7. Move app route wiring to domain router imports while keeping legacy facades.
8. Remove compatibility facades only after import inventories and route snapshots prove no behavior drift.

## Test Commands

Run the device operations boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_status_lifecycle.py -q
```

Run the pairing, polling, and reporting response-shape checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_pairing.py server/tests/test_device_operations_polling_reporting.py -q
```

Run the existing device compatibility checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py -q
```

Run the script asset and content bridge response-shape checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_uploads.py server/tests/test_device_operations_content_bridge.py server/tests/test_content_api.py server/tests/test_collection_builder.py server/tests/test_dm_sequences_api.py -q
```

## Compatibility Cleanup Gates

Do not remove `app.routers.device` or `app.routers.devices` until all of these are true:

- `rg "app\.routers\.(device|devices)|from app\.routers import (device|devices)" server/app server/tests` returns only approved compatibility shims, README entries, and cleanup tests.
- `server/tests/test_device_operations_auth_parity.py` passes against the domain routers.
- `server/tests/test_device_operations_router_facade.py` proves old and new router import paths expose the same route objects during the alias phase.
- `app.main` imports device operations routers and lifecycle functions from `app.domains.device_operations`.
- Release notes mention the import-path migration.

Do not move the content, collection, or DM bridge out of this domain until a `content_collection` plan and tests own that transfer.
