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
- Creative patch mutation stays in `app.services.agency_creative_patch_service`.
- Provider reservation accounting stays in
  `app.services.provider_cost_reservation_service`.

## Current Modules

- `agency_router.py` owns all `/api/agency/*` route handlers, agency response
  shaping, `_redact_model_config_snapshot`, repair task summaries, retry action
  decisions, `repair-tasks` endpoints, and paid repair authorization endpoints.
- `agency_manifest.py` owns `AgencyManifest`, `AgencyManifestError`,
  `EXPERT_IDS`, manifest loading, expert markdown hash checks, legacy expert
  lookup, and manifest verification.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.agency` | `app.domains.agency_operations.agency_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.agency_manifest` | `app.domains.agency_operations.agency_manifest` | Keep while dirty service modules have approved compatibility imports; remove only after import inventory shows no production legacy imports. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-only access checks for expert, invocation, creative patch,
  multimodal review, and repair task endpoints.
- Preserve secret redaction for model snapshots.
- Preserve repair retry and paid authorization budget semantics.
- Preserve monkeypatch compatibility for `app.routers.agency` during the alias
  phase.
- Preserve monkeypatch compatibility for `app.services.agency_manifest` while
  dirty service modules keep approved compatibility imports.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `agency_router` from `app.domains.agency_operations`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing agency API, console, repair, and runtime tests pass.
- Import inventory shows no unapproved production imports of `app.routers.agency`.

Do not remove the legacy agency manifest facade until all of these are true:

- `rg "app\.services\.agency_manifest" server/app server/tests` returns only
  compatibility tests, migration docs, or service modules whose domains have not
  moved yet.
- Direct domain manifest coverage proves `AgencyManifest`, expert lookup,
  markdown hash checks, legacy expert lookup, and `verify_manifest` behavior.
- Domain-owned production modules import
  `app.domains.agency_operations.agency_manifest` directly.
