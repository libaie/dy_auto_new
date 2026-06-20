# Script Output ORM Boundary Design

## Context

`EpisodeScript`, `ScriptDramaticBeat`, `ScriptSceneOutline`, and
`ScriptVisualShot` are structured script pipeline output tables, but their
class bodies still live in `app.db_models`.

## Decision

Move these four class bodies to `app.db.models.script_pipeline`, next to
`PipelineRun`. Keep the legacy `app.db_models` names as compatibility
re-exports. Update the script pipeline owner service and the AI video series
model facade to import the new model path.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_output_orm_boundary.py server/tests/test_script_pipeline_domain_boundary.py server/tests/test_ai_video_series_orm_boundary.py server/tests/test_script_pipeline.py::test_script_sqlalchemy_tables_persist_structured_rows -q
```
