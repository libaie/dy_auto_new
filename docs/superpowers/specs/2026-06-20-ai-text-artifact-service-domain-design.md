# AI Text Artifact Service Domain Design

Status: auto-approved.

## Context

`app.domains.ai_text_artifacts` already owns the `/api/ai-text-artifacts/*` router, but the versioning, approval, lineage, regeneration, and run-consumption business logic still lives in `app.services.ai_text_artifact_service`. That leaves the domain HTTP surface separated from the core domain service it delegates to.

## Decision

Move the full implementation to `app.domains.ai_text_artifacts.ai_text_artifact_service` and keep `app.services.ai_text_artifact_service` as a thin `sys.modules` compatibility facade.

This preserves behavior for existing callers while letting domain modules use the new owner path. The facade remains until legacy imports in services and tests are intentionally cleaned up.

## Scope

In scope:

- Create `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py` with the current `AITextArtifactService` implementation and artifact consumption constants.
- Replace `server/app/services/ai_text_artifact_service.py` with a compatibility facade.
- Update domain-owned production modules to import `AITextArtifactService` from `app.domains.ai_text_artifacts.ai_text_artifact_service`.
- Update `server/app/domains/ai_text_artifacts/README.md` so it records service ownership, the facade register, and cleanup gates.
- Add focused tests proving the old and new service import paths are the same module object.

Out of scope:

- No behavior changes to artifact versioning, approval, stale approval checks, regeneration, lineage, consumer binding, or legacy run backfill.
- No schema changes.
- No API response-shape changes.
- No cleanup of non-domain service imports in `app.services.*` modules during this step.

## Architecture

The domain service owns:

- `AITextArtifactService`
- `SERIES_RUN_ARTIFACT_TYPES`
- `EPISODE_RUN_ARTIFACT_TYPES`
- `ARTIFACT_CONSUMPTION_ORDER`

The legacy service module imports the domain service module, replaces itself in `sys.modules`, and updates globals so old imports and monkeypatches continue to target the same module object.

Domain modules that call the service use the domain path:

- `app.domains.ai_text_artifacts.ai_text_artifacts_router`
- `app.domains.ai_video_series.artifacts`
- `app.domains.ai_video_series.read_models`
- `app.domains.ai_video_series.series_planning_service`
- `app.domains.ai_video_series.style_lock`
- `app.domains.director_planning.director_router`
- `app.domains.video_production.video_production_router`

## Data Flow

Routes and other domains instantiate `AITextArtifactService(db)` from the AI text artifacts domain. The service still reads and writes `AITextArtifact` and `AITextArtifactConsumer`, computes versions, supersedes older approvals, binds approved artifacts to production runs, and backfills legacy run artifacts exactly as before.

## Error Handling

Error behavior is unchanged. Missing artifacts still raise `ValueError("artifact_not_found")`, stale approvals still raise `ValueError("stale_artifact_version")`, missing run/series/episode during backfill keeps the existing value errors, and AI regeneration continues to surface existing model errors through callers.

## Testing

Add `server/tests/test_ai_text_artifact_service_domain_facade.py` to verify:

- this spec and plan mention `app.domains.ai_text_artifacts.ai_text_artifact_service`, `app.services.ai_text_artifact_service`, `AITextArtifactService`, and `ARTIFACT_CONSUMPTION_ORDER`;
- the domain service file exists;
- the legacy service file is a thin facade with no copied business implementation;
- old and new imports resolve to the same module object and expose identical public service objects;
- all domain-owned production modules import the domain service path;
- the AI text artifacts README records service ownership, facade mapping, and cleanup gate.

Run the new boundary test with focused artifact and series coverage:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_service_domain_facade.py server/tests/test_ai_text_artifacts_domain_boundary.py server/tests/test_ai_text_artifact_service.py server/tests/test_ai_text_artifacts_api.py server/tests/test_series_planning_service.py -q
```
