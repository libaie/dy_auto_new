# UI Selector ORM Boundary Plan

> Auto-approved spec: proceed without approval pause.

**Goal:** Move the standalone `UISelector` ORM class body out of
`app.db_models`.

## Tasks

- [ ] Add a boundary test for `app.db.models.selector_management.UISelector`.
- [ ] Move `UISelector` into `server/app/db/models/selector_management.py`.
- [ ] Re-export `UISelector` from `server/app/db_models.py`.
- [ ] Update selector-management domain imports and README.
- [ ] Run focused selector tests.
