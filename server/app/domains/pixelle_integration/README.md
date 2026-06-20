# Pixelle Integration Domain

This domain owns the Pixelle-Video configuration bridge and transparent proxy
routes.

## Owned Routes

- `/api/pixelle/*`
- `/api/pixelle-proxy/*`

## Not Owned

- `AIModel` and `SystemSetting` ORM model definitions stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Runtime model resolution stays in shared services.
- Pixelle execution orchestration stays in `app.services.pixelle_execution_service`.
- Video production orchestration stays in its own router and services.

## Current Modules

- `pixelle_router.py` owns `PixelleConfigUpdate`, `router`, `proxy_router`,
  `_serialize_ai_models`, `_redact_secrets`, `_get_proxy_client`,
  `_pixelle_headers`, config bridge read/write helpers, template preview
  serving, test-connection handling, and transparent proxy forwarding.
- `pixelle_client.py` owns `DEFAULT_BASE_URL`, Pixelle base URL/API key lookup,
  lazy `httpx.AsyncClient`, `_pixelle_request`, retries, JSON parsing, and
  `close_client`.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.pixelle` | `app.domains.pixelle_integration.pixelle_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.pixelle_client` | `app.domains.pixelle_integration.pixelle_client` | Keep while `app.main` shutdown and not-yet-moved service modules have approved compatibility imports; remove only after import inventory shows no production legacy imports. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve recursive secret redaction and model serialization behavior.
- Preserve monkeypatch compatibility for `app.routers.pixelle._get_proxy_client`.
- Preserve both exported routers: `router` and `proxy_router`.
- Preserve monkeypatch compatibility for `app.services.pixelle_client` while
  shutdown and not-yet-moved service modules keep approved compatibility
  imports.
- Keep video-library and video-production ownership outside this domain.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `pixelle_router` from `app.domains.pixelle_integration`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing Pixelle config/proxy tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.pixelle`.

Do not remove the legacy Pixelle client facade until all of these are true:

- `rg "app\.services\.pixelle_client|from app\.services import pixelle_client" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- Direct domain client coverage proves `_get_base_url`, `_pixelle_request`,
  retry behavior, JSON parsing, API key lookup, no-proxy client creation, and
  `close_client` behavior.
- Domain-owned production modules import
  `app.domains.pixelle_integration.pixelle_client` directly.
