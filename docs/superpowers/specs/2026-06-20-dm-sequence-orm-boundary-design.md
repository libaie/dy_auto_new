# DM Sequence ORM Boundary Design

## Context

`DMSequence` is the content-collection DM template table, but its class body
still lives in the monolithic `app.db_models` module.

## Decision

Move `DMSequence` to `app.db.models.content_collection`. Keep
`app.db_models.DMSequence` as a compatibility re-export. Leave collected
comment/user/conversation models in `app.db_models` for a later graph slice.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py server/tests/test_content_collection_mutations.py server/tests/test_dm_sequences_api.py server/tests/test_dm_sequence_visibility_domain_import.py server/tests/test_device_endpoints.py -q
```
