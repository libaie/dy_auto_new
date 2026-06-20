# Pipeline Run ORM Boundary Design

## Context

`PipelineRun` is the persistence model for the script pipeline runtime, but its
class body still lives in the monolithic `app.db_models` module. The
`script_pipeline` domain already owns the pipeline route and service logic.

## Decision

Move `PipelineRun` to `app.db.models.script_pipeline`. Keep
`app.db_models.PipelineRun` as a compatibility re-export. Update the script
pipeline owner domain and AI video series model facade to import the new model
path. Leave wider cross-domain readers on the compatibility path for later
focused slices.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pipeline_run_orm_boundary.py server/tests/test_script_pipeline_domain_boundary.py server/tests/test_ai_video_series_orm_boundary.py server/tests/test_pipeline_saved_storyboard_compat.py -q
```
