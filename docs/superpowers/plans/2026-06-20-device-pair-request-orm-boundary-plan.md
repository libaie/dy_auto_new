# Device Pair Request ORM Boundary Plan

> Auto-approved spec: proceed without approval pause.

**Goal:** Move the standalone `DevicePairRequest` ORM class body out of
`app.db_models`.

## Tasks

- [ ] Add a boundary test for `app.db.models.device_operations.DevicePairRequest`.
- [ ] Move the class body to `server/app/db/models/device_operations.py`.
- [ ] Import and re-export the moved class from `server/app/db_models.py`.
- [ ] Document the ORM boundary in the device operations README.
- [ ] Run the focused pairing/admin-device tests.
