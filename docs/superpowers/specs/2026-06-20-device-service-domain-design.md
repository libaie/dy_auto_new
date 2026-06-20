# Device Service Domain Design

Date: 2026-06-20

## Goal

Move device registration, heartbeat, status lookup, and offline marking from
`app.services.device_service` into `app.domains.device_operations.device_service`
without changing `/api/device/*`, `/api/devices/*`, polling, heartbeat, or
status websocket behavior.

## Approved Approach

Move `server/app/services/device_service.py` to
`server/app/domains/device_operations/device_service.py`.

Keep `app.services.device_service` as a `sys.modules` compatibility facade.
Device operation modules import the domain service directly. Existing tests can
continue to import the legacy path to prove compatibility.

## Boundaries

- Preserve `DeviceService` and `device_service`.
- Preserve register/update fields, heartbeat return value, status dictionary,
  proxy config passthrough, and offline timeout behavior.
- Do not move route ownership, websocket ownership, task polling logic,
  admin route behavior, ORM models, or status lifecycle in this slice.

## Target Structure

```text
server/app/domains/device_operations/
  device_service.py
  device_router.py
  polling.py
  reporting.py
  status_ws.py

server/app/services/
  device_service.py  # compatibility facade
```

## Verification

- Add a boundary test proving this spec and plan mention the domain module,
  legacy facade, and `DeviceService`.
- Prove the domain file exists and the legacy file is a thin facade.
- Prove legacy and domain imports resolve to the same module object.
- Prove device operation modules import the domain service directly.
- Run device service and device operations compatibility tests after migration.
