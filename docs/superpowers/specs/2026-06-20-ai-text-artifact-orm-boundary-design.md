# AI Text Artifact ORM Boundary Design

## Context

`AITextArtifact` and `AITextArtifactConsumer` are owned by the
`ai_text_artifacts` business domain, but their class bodies still live in the
monolithic `app.db_models` module.

## Decision

Move both ORM class bodies to `app.db.models.ai_text_artifacts`. Keep
`app.db_models.AITextArtifact` and `app.db_models.AITextArtifactConsumer` as
compatibility re-exports. Update the owner domain service and router to import
the new model path. Leave wider cross-domain consumers on the compatibility
path for later focused slices.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_orm_boundary.py server/tests/test_ai_text_artifacts_domain_boundary.py server/tests/test_ai_text_artifact_service_domain_facade.py server/tests/test_ai_video_series_orm_boundary.py -q
```
