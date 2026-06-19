# Seedance Integration Domain Design

Status: auto-approved.

## Goal

Move the `/api/seedance/*` and `/api/seedance-proxy/*` HTTP surfaces into
`app.domains.seedance_integration` while preserving Seedance task submission,
task polling, API key lookup, shared client reuse, and proxy behavior.

## Domain Boundary

The new domain owns:

- `app.domains.seedance_integration.seedance_router`
- `seedance_router.py`
- `/api/seedance/generate`
- `/api/seedance/task/{task_id}`
- `/api/seedance-proxy/{path:path}`
- `/api/seedance-proxy/`

The domain owns the current integration constants and helpers:

- `SEEDANCE_API_URL`
- `SEEDANCE_MODEL_ID`
- `PROXY_METHODS`
- `SeedanceGenerateRequest`
- `_get_api_key`
- `_get_client`
- `_do_proxy`

## Compatibility

Keep `app.routers.seedance` as a thin facade that aliases to
`app.domains.seedance_integration.seedance_router` through `sys.modules`.
Existing tests and monkeypatches such as `app.routers.seedance._get_client`
must resolve to the same module object while the facade exists.

## Security And Behavior

- Preserve `require_role("admin")` on all API and proxy routes.
- Preserve API key lookup from `SEEDANCE_API_KEY` and `SystemSetting`.
- Preserve stripped request/response header policy for proxying.
- Preserve `httpx.ConnectError`, timeout, and request error HTTP mappings.
- Preserve `api_router` and `proxy_router` as separate APIRouter exports.

## Exit Criteria

- `app.main` imports `seedance_router` from
  `app.domains.seedance_integration`.
- `app.main` includes `seedance_router.api_router` and
  `seedance_router.proxy_router`, not `seedance.api_router` or
  `seedance.proxy_router`.
- Route/auth snapshots show endpoint modules under
  `app.domains.seedance_integration.seedance_router`.
- `app.routers.seedance` remains a <=20 line facade with no `APIRouter`.
- Focused Seedance route/proxy tests pass.
