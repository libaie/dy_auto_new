# Replied Comment ORM Boundary Design

## Context

`RepliedComment` is a standalone content-collection dedupe table still defined
in the monolithic `app.db_models` module.

## Decision

Move the `RepliedComment` class body to `app.db.models.content_collection`.
Keep `app.db_models.RepliedComment` as a compatibility re-export. Leave the
larger collected comment/user/conversation graph in `app.db_models`.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py server/tests/test_content_collection_domain_boundary.py server/tests/test_content_collection_device_bridge.py server/tests/test_device_endpoints.py -q
```
