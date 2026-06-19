# Seedance Integration Domain Plan

Status: auto-approved.

## Success Criteria

Seedance API and proxy routes are available from
`app.domains.seedance_integration.seedance_router` with unchanged paths, auth
dependencies, request models, constants, and helper monkeypatch compatibility.

## Steps

1. Add boundary tests.
   Verify: spec/plan mention `app.domains.seedance_integration`,
   `seedance_router.py`, `app.routers.seedance`, `/api/seedance`,
   `/api/seedance-proxy`, `SeedanceGenerateRequest`, `SEEDANCE_MODEL_ID`,
   `_get_api_key`, `_get_client`, and `_do_proxy`.

2. Add legacy facade tests.
   Verify: importing `app.routers.seedance` and
   `app.domains.seedance_integration.seedance_router` returns the same module
   object and exposes both `api_router` and `proxy_router`.

3. Add route/auth parity tests.
   Verify: all Seedance API/proxy routes keep `require_role("admin")` and
   endpoint modules move to `app.domains.seedance_integration.seedance_router`.

4. Move router implementation.
   Verify: create `app.domains.seedance_integration`, copy the current router
   into `seedance_router.py`, and replace the legacy router with a `sys.modules`
   facade.

5. Wire app startup directly to the domain.
   Verify: `app.main` imports and includes `seedance_router.api_router` and
   `seedance_router.proxy_router`.

6. Run focused regression.
   Verify: new domain tests plus existing Seedance backend closure tests pass
   before committing.
