# User ORM Boundary Design

## Context

`User` is the identity-access user table, but its class body still lives in the
monolithic `app.db_models` module.

## Decision

Move the `User` class body to `app.db.models.identity_access`. Keep
`app.db_models.User` as a compatibility re-export. Leave `Device` in
`app.db_models` because it is still tied to the device/account/task graph.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_identity_access_orm_boundary.py server/tests/test_identity_access_domain_boundary.py server/tests/test_identity_access_router_facade.py server/tests/test_admin_auth.py -q
```
