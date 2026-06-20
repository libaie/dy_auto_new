# Audit Report ORM Boundary Design

## Context

`AuditReport` is a standalone quality-audit table still defined in the
monolithic `app.db_models` module.

## Decision

Move the `AuditReport` class body to `app.db.models.quality_audit`. Keep
`app.db_models.AuditReport` as a compatibility re-export.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_quality_audit_orm_boundary.py server/tests/test_audit_router_payload.py server/tests/test_quality_audit_router_facade.py server/tests/test_quality_audit_gate_facade.py -q
```
