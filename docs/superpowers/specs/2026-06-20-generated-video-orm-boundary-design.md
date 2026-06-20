# Generated Video ORM Boundary Design

## Context

`GeneratedVideo` is the generated-video library table, but its class body still
lives in the monolithic `app.db_models` module.

## Decision

Move `GeneratedVideo` to `app.db.models.video_library`. Keep
`app.db_models.GeneratedVideo` as a compatibility re-export. Leave
`PipelineRun`, `Episode`, and `Series` in their current domain/legacy model
paths.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_library_orm_boundary.py server/tests/test_video_library_domain_boundary.py server/tests/test_video_library_router_facade.py server/tests/test_video_library_api.py server/tests/test_script_pipeline_router_facade.py server/tests/test_ai_video_series_status_read_model.py server/tests/test_video_production_final_gate.py -q
```
