# Pixelle Integration Domain Design

## Goal

Move the legacy Pixelle-Video config bridge and transparent proxy router into a
business-domain package without changing route behavior, secret handling,
downstream headers, proxy behavior, or monkeypatch compatibility.

## Approved Approach

Use the established facade-first migration pattern:

1. Create `app.domains.pixelle_integration`.
2. Move the current `app.routers.pixelle` implementation to
   `app.domains.pixelle_integration.pixelle_router` in `pixelle_router.py`.
3. Replace `app.routers.pixelle` with a thin `sys.modules` compatibility
   facade pointing at the domain router module.
4. Wire `app.main` directly to both `pixelle_router.router` and
   `pixelle_router.proxy_router`.

## Ownership Boundary

`app.domains.pixelle_integration` owns:

- `GET /api/pixelle/config`
- `PUT /api/pixelle/config`
- `GET /api/pixelle/template-preview/{size}/{filename}`
- `GET /api/pixelle/test-connection`
- all `/api/pixelle-proxy/*` methods
- `PixelleConfigUpdate`
- Pixelle config file read/write helpers
- secret redaction helpers such as `_redact_secrets`
- AI model serialization for Pixelle config bridge through `_serialize_ai_models`
- Pixelle API key/header helpers and proxy client lifecycle helpers

`app.domains.pixelle_integration` does not own:

- `AIModel` or `SystemSetting` ORM definitions.
- DB session construction.
- Auth dependencies.
- Runtime model resolution for production stages.
- Pixelle execution service logic in `app.services.pixelle_execution_service`.
- Generic Pixelle HTTP client logic in `app.services.pixelle_client`.
- Video production orchestration.

## Compatibility Contract

The migration must preserve:

- Route paths, methods, names, dependency names, and response shapes.
- Both router exports: `router` and `proxy_router`.
- Recursive secret redaction behavior.
- `_serialize_ai_models` import compatibility.
- `_get_proxy_client` monkeypatch compatibility through `app.routers.pixelle`.
- `_pixelle_headers` and DB-backed `pixelle_api_key` behavior.
- Template preview image token behavior.
- Proxy header stripping and downstream `X-API-Key` injection.

## Testing Strategy

Add boundary tests that fail before the move and pass after domain wiring:

- Spec and plan mention the domain, facade, both route prefixes,
  `PixelleConfigUpdate`, `_serialize_ai_models`, `_redact_secrets`, and
  `_get_proxy_client`.
- Domain package exports `DOMAIN_NAME`, `PUBLIC_ROUTE_PREFIX`, and
  `PUBLIC_PROXY_PREFIX`.
- Domain README documents facade and cleanup gates.
- Legacy `app.routers.pixelle` is a thin `sys.modules` facade.
- Legacy and domain imports resolve to the same module object.
- Router snapshot matches current `/api/pixelle/*` and `/api/pixelle-proxy/*`
  routes.
- FastAPI route table uses `app.domains.pixelle_integration.pixelle_router`
  endpoint modules.

Run existing Pixelle config serialization, config security, and video studio
proxy backend tests after migration.

## Cleanup Gates

Do not remove `app.routers.pixelle` until all of these are true:

- `app.main` imports `pixelle_router` from `app.domains.pixelle_integration`.
- Route/auth snapshots pass against the domain endpoint module.
- Existing Pixelle config/proxy tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.pixelle`.
- Tests that monkeypatch the legacy module path are either updated or
  intentionally kept compatible through the alias phase.
