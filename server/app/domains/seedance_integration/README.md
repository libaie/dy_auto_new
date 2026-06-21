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
- Model registry and provider selection stay in their existing model
  configuration and production domains.

## Current Modules

- `seedance_router.py` owns `SeedanceGenerateRequest`, `SEEDANCE_API_URL`,
  `SEEDANCE_MODEL_ID`, `PROXY_METHODS`, `_get_api_key`, `_get_client`,
  `_do_proxy`, `api_router`, and `proxy_router`.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-role protection on every API and proxy route.
- Preserve API key lookup from env and `SystemSetting`.
- Preserve client reuse semantics keyed by API key.
- Preserve proxy header stripping and upstream error mapping.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
