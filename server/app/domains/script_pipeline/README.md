# Script Pipeline Domain

This domain owns the legacy script-to-video pipeline HTTP routes.

## Owned Routes

- `/api/pipeline/*`

## Not Owned

- ORM models such as `PipelineRun`, `Episode`, `GeneratedVideo`, and `Series`
  stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Role dependencies stay in `app.deps`.
- Pixelle transport stays in `app.services.pixelle_client`.
- Agency orchestration internals stay in `app.services`.
- Script text generation service code stays in `app.services.script_pipeline`.
- Series authoring, AI text artifact, director, and video production routes stay
  in their own routers or domains.

## Current Modules

- `pipeline_router.py` owns `PipelineStartRequest`, `/api/pipeline/*` route
  handlers, `_submit_and_poll`, `_run_all_layers`, run serialization, agency
  trace status helpers, and route-local Pixelle pipeline orchestration helpers.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.pipeline` | `app.domains.script_pipeline.pipeline_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve saved `Episode.storyboard_json` startup compatibility.
- Preserve monkeypatch compatibility for `_submit_and_poll`.
- Preserve direct call compatibility for `_run_all_layers`.
- Keep service-layer `app.services.script_pipeline` independent from this
  route domain.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `pipeline_router` from `app.domains.script_pipeline`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing saved-storyboard and agency console pipeline tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.pipeline`.
