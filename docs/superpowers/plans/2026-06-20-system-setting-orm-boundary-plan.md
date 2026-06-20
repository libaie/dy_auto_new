# System Setting ORM Boundary Plan

> Auto-approved spec: proceed without approval pause.

**Goal:** Move the standalone `SystemSetting` ORM class body out of
`app.db_models`.

## Tasks

- [ ] Add a boundary test for `app.db.models.system_configuration.SystemSetting`.
- [ ] Move the class body to `server/app/db/models/system_configuration.py`.
- [ ] Re-export `SystemSetting` from `server/app/db_models.py`.
- [ ] Update the system configuration router and README to use/document the ORM boundary.
- [ ] Run focused settings/config tests.
