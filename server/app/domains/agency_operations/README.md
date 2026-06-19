# Agency Operations Domain

This domain owns agency transparency, creative patch, multimodal review, and
repair task routes.

## Owned Routes

- `/api/agency/*`

## Not Owned

- Agency ORM models such as `AgencyExpertInvocation` and `AgencyCreativePatch`
  stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Agency manifest loading stays in `app.services.agency_manifest`.
- Creative patch mutation stays in `app.services.agency_creative_patch_service`.
- Provider reservation accounting stays in
  `app.services.provider_cost_reservation_service`.

## Current Modules

- `agency_router.py` owns all `/api/agency/*` route handlers, agency response
  shaping, `_redact_model_config_snapshot`, repair task summaries, retry action
  decisions, `repair-tasks` endpoints, and paid repair authorization endpoints.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.agency` | `app.domains.agency_operations.agency_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-only access checks for expert, invocation, creative patch,
  multimodal review, and repair task endpoints.
- Preserve secret redaction for model snapshots.
- Preserve repair retry and paid authorization budget semantics.
- Preserve monkeypatch compatibility for `app.routers.agency` during the alias
  phase.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `agency_router` from `app.domains.agency_operations`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing agency API, console, repair, and runtime tests pass.
- Import inventory shows no unapproved production imports of `app.routers.agency`.
