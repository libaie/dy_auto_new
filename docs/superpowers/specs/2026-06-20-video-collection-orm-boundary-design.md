# Video Collection ORM Boundary Design

## Context

`VideoCollection` is the video-production episode packaging table, but its
class body still lives in the monolithic `app.db_models` module.

## Decision

Move `VideoCollection` to `app.db.models.video_production`. Keep
`app.db_models.VideoCollection` as a compatibility re-export. Leave the larger
production run, plan, job, asset, and review graph in `app.db_models`.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_orm_boundary.py server/tests/test_collection_builder.py server/tests/test_asset_lifecycle_service.py server/tests/test_video_production_collection_service_facade.py -q
```
