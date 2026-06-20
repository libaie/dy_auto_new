# Audit Report ORM Boundary Plan

> Auto-approved spec: proceed without approval pause.

**Goal:** Move the standalone `AuditReport` ORM class body out of
`app.db_models`.

## Tasks

- [ ] Add a boundary test for `app.db.models.quality_audit.AuditReport`.
- [ ] Move `AuditReport` into `server/app/db/models/quality_audit.py`.
- [ ] Re-export `AuditReport` from `server/app/db_models.py`.
- [ ] Update quality-audit domain imports and README.
- [ ] Run focused quality-audit tests.
