# Device ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move the `Device` ORM class body from `app.db_models` into
`app.db.models.device_operations`.

## Design

- `app.db.models.device_operations` owns `Device` and `DevicePairRequest`.
- `app.db_models.Device` remains a compatibility re-export.
- Device operations domain modules should import `Device` and
  `DevicePairRequest` from `app.db.models.device_operations`.
- Shared callers outside the device operations domain may keep using
  `app.db_models.Device` in this slice.

## Out Of Scope

- Do not move `Account`, `Task`, account groups, chains, or content models.
- Do not change routes, response shapes, auth behavior, websocket behavior, or
  database schema.

## Verification

- Extend the device operations ORM boundary test to cover `Device`.
- Run focused device operations tests that exercise device service, pairing,
  admin device APIs, and ORM import compatibility.
