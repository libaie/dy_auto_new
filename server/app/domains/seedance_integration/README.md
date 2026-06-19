# Seedance Integration Domain

This domain owns the Seedance Ark API and proxy routes.

## Owned Routes

- `/api/seedance/generate`
- `/api/seedance/task/{task_id}`
- `/api/seedance-proxy/{path:path}`
- `/api/seedance-proxy/`

## Not Owned

- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Persistent settings storage stays in `app.db_models.SystemSetting`.
- Model registry and provider selection stay in their existing model
  configuration and production domains.

## Current Modules

- `seedance_router.py` owns `SeedanceGenerateRequest`, `SEEDANCE_API_URL`,
  `SEEDANCE_MODEL_ID`, `PROXY_METHODS`, `_get_api_key`, `_get_client`,
  `_do_proxy`, `api_router`, and `proxy_router`.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.seedance` | `app.domains.seedance_integration.seedance_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-role protection on every API and proxy route.
- Preserve API key lookup from env and `SystemSetting`.
- Preserve client reuse semantics keyed by API key.
- Preserve proxy header stripping and upstream error mapping.
- Preserve compatibility for monkeypatches against `app.routers.seedance`.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `seedance_router` from
  `app.domains.seedance_integration`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing Seedance backend closure tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.seedance`.
