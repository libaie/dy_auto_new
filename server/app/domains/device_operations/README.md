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

## Ownership Rules

- `app.domains.device_operations` owns the target migration boundary for `/api/device/*` and `/api/devices/*`.
- `app.routers.device` remains the compatibility entrypoint for `/api/device/*` until the router facade gate lands.
- `app.routers.devices` remains the compatibility entrypoint for `/api/devices/*` until the admin router facade gate lands.
- `server/app/main.py::_offline_checker` remains in `app.main` until lifecycle behavior is moved behind `status_lifecycle.py`.
- Content, collection, and DM endpoints under `/api/device/*` are a temporary bridge; final business ownership belongs to a future `content_collection` domain.
- Domain non-router modules must avoid FastAPI imports unless they are route assembly modules.

## Facade Register

| Facade | Target | Introduced | Exit condition |
|---|---|---|---|
| `app.routers.device` | `app.domains.device_operations.device_router` | Planned PR3 | Route/auth/websocket snapshots pass with the domain router and all callers have an explicit compatibility path. |
| `app.routers.devices` | `app.domains.device_operations.admin_router` | Planned PR3 | Admin device route and pair-event websocket snapshots pass with the domain router and all callers have an explicit compatibility path. |
| `app.main._offline_checker` | `app.domains.device_operations.status_lifecycle` | Planned PR5 | Lifecycle tests cover heartbeat drain, DB flush, requeue, offline broadcast, stuck task handling, and lifespan start/stop through the domain entrypoint. |
| `/api/device/*` content and DM bridge handlers | Future `content_collection` domain adapters | Deferred | `content_collection` owns those business use cases and adapter tests prove unchanged device response shapes. |

## Migration Checklist

1. Characterize current route/auth/websocket and offline lifecycle behavior.
2. Add this metadata-only domain skeleton.
3. Move legacy router behavior behind `device_router.py` and `admin_router.py` with compatibility facades.
4. Split pairing, status websocket, polling, reporting, script assets, and bridge behavior into focused modules.
5. Move the offline checker into `status_lifecycle.py` after lifecycle tests cover the behavior.
6. Remove compatibility facades only after import inventories and route snapshots prove no behavior drift.

## Test Commands

Run the device operations boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_status_lifecycle.py -q
```

Run the existing device compatibility checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py -q
```

## Compatibility Cleanup Gates

Do not remove `app.routers.device` or `app.routers.devices` until all of these are true:

- `rg "app\.routers\.(device|devices)|from app\.routers import (device|devices)" server/app server/tests` returns only approved compatibility shims, README entries, and cleanup tests.
- `server/tests/test_device_operations_auth_parity.py` passes against the domain routers.
- `server/tests/test_device_operations_router_facade.py` proves old and new router import paths expose the same route objects during the alias phase.
- `app.main` imports device operations lifecycle functions from `app.domains.device_operations`.
- Release notes mention the import-path migration.

Do not move the content, collection, or DM bridge out of this domain until a `content_collection` plan and tests own that transfer.
