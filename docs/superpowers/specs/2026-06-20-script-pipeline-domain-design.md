# Script Pipeline Domain Design

## Goal

Move the legacy `/api/pipeline/*` router into a business-domain package without
changing HTTP paths, route names, auth dependencies, response payloads, or the
existing Pixelle/agency orchestration behavior.

## Approved Approach

Use the same facade-first domain migration pattern already used by
`identity_access`, `system_configuration`, `video_library`, and other migrated
domains.

1. Create `app.domains.script_pipeline`.
2. Move the current `app.routers.pipeline` implementation to
   `app.domains.script_pipeline.pipeline_router` in `pipeline_router.py`.
3. Replace `app.routers.pipeline` with a thin `sys.modules` compatibility
   facade pointing at the domain router module.
4. Wire `app.main` directly to `pipeline_router.router`.
5. Preserve legacy imports such as `from app.routers import pipeline` for tests,
   scripts, and callers that still patch route-local helpers like
   `_submit_and_poll` or call `_run_all_layers`.

## Ownership Boundary

`app.domains.script_pipeline` owns:

- `POST /api/pipeline/start`
- `GET /api/pipeline/runs/{series_id}`
- `GET /api/pipeline/runs/by-id/{run_id}`
- `GET /api/pipeline/runs/{series_id}/{run_id}`
- Route-local request models and helper functions currently in
  `pipeline.py`, including `PipelineStartRequest`, `_serialize_run`,
  `_run_all_layers`, `_submit_and_poll`, and agency trace helpers.

`app.domains.script_pipeline` does not own:

- ORM models such as `PipelineRun`, `Episode`, `GeneratedVideo`, and `Series`;
  those remain in `app.db_models`.
- Database session construction; `SessionLocal` and `get_db` remain in
  `app.database`.
- Role checks; `require_role` remains in `app.deps`.
- Pixelle client transport; `_pixelle_request` remains in
  `app.services.pixelle_client`.
- Agency orchestration internals; `AgencyOrchestrator`,
  `resolve_runtime_model_config`, and `build_agency_context` remain in
  `app.services`.
- Text-script generation service code in `app.services.script_pipeline`; that
  module keeps its current service-layer role and must not import the domain
  router.
- Series authoring and AI text artifact routes, including `ai_video_series`,
  `ai_text_artifacts`, `director`, and `video_production`.

## Compatibility Contract

The migration must preserve:

- Route paths, methods, names, and dependency names.
- Endpoint behavior for saved `Episode.storyboard_json` compatibility.
- Ability to monkeypatch `app.routers.pipeline._submit_and_poll` in existing
  tests.
- Ability to call `app.routers.pipeline._run_all_layers` in existing tests.
- `PipelineRun.layers_json` and `agency_trace_status` serialization.
- Pixelle polling circuit breaker state during the alias phase.

## Testing Strategy

Add boundary tests that fail before the move and pass after the domain package
exists:

- Spec and plan mention the domain, facade, routes, and non-owned services.
- Domain package exports `DOMAIN_NAME` and `PUBLIC_ROUTE_PREFIX`.
- Domain README documents facade and cleanup gates.
- Legacy router file is a thin facade without its own `APIRouter`.
- Legacy and domain module imports resolve to the same module object.
- Router snapshot matches the four existing `/api/pipeline/*` routes.
- `app.main` registers the domain endpoint module directly and registers each
  route once.

Run existing saved-storyboard and agency pipeline tests as focused behavioral
coverage after the move.

## Cleanup Gates

Do not remove `app.routers.pipeline` until all of these are true:

- `app.main` imports `app.domains.script_pipeline.pipeline_router` directly.
- Route snapshot tests prove domain endpoint modules are registered.
- Legacy import inventory shows only approved compatibility references remain.
- Tests that patch `_submit_and_poll` or call `_run_all_layers` are updated or
  intentionally kept compatible.
- Existing `/api/pipeline/start` saved-storyboard behavior remains covered.
