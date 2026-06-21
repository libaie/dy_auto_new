# Device Operations Domain

This domain will own device pairing, device status websockets, task polling,
device reporting, script assets, and the admin device management surface.

## Ownership Rules

- `app.domains.device_operations` owns the target migration boundary for `/api/device/*` and `/api/devices/*`.
- `app.domains.device_operations.pairing` owns device pair request/status and pair-status websocket behavior.
- `app.domains.device_operations.status_ws` owns the device status websocket and pending-task websocket notification helper.
- `app.domains.device_operations.polling` owns device task polling, cancellation delivery, DM sequence sync, and poll response shaping.
- `app.domains.device_operations.reporting` owns task progress, task result, stats increment, heartbeat, and risk-control reporting.
- `app.domains.device_operations.script_assets` owns selectors, prompt-template sync, script packages, template images, and calibration uploads.
- `app.domains.device_operations.script_service` owns `ScriptService`, `script_service`, script zip upload/download, and version storage under SERVER_DIR / `scripts`.
- `app.domains.device_operations.content_bridge` temporarily owns device-authenticated bridges for content generation, AI proxy, collection reports, comment replies, DM flows, user profiles, and avatars.
- `app.domains.device_operations.status_lifecycle` owns heartbeat flush, stale-device offline marking, stuck-task handling, and channel item reset behavior.
- `app.domains.device_operations.device_service` owns `DeviceService` registration, heartbeat, status lookup, and offline marking.
- `app.db.models.device_operations` owns the `Device` and `DevicePairRequest` ORM class bodies.
- `server/app/main.py::_offline_checker` remains as a thin lifespan-compatible wrapper around `status_lifecycle.offline_checker`.
- Content, collection, and DM endpoints under `/api/device/*` are a temporary bridge; final business ownership belongs to a future `content_collection` domain.
- Domain non-router modules must avoid FastAPI imports unless they are route assembly modules.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Test Commands

Run the device operations boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_status_lifecycle.py -q
```

Run the pairing, polling, and reporting response-shape checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_pairing.py server/tests/test_device_operations_polling_reporting.py -q
```


```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py -q
```

Run the script asset and content bridge response-shape checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_uploads.py server/tests/test_device_operations_content_bridge.py server/tests/test_content_api.py server/tests/test_collection_builder.py server/tests/test_dm_sequences_api.py -q
```

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
