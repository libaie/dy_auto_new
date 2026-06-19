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
- Generic Pixelle client calls stay in `app.services.pixelle_client`.
- Video production orchestration stays in its own router and services.

## Current Modules

- `pixelle_router.py` owns `PixelleConfigUpdate`, `router`, `proxy_router`,
  `_serialize_ai_models`, `_redact_secrets`, `_get_proxy_client`,
  `_pixelle_headers`, config bridge read/write helpers, template preview
  serving, test-connection handling, and transparent proxy forwarding.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.pixelle` | `app.domains.pixelle_integration.pixelle_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve recursive secret redaction and model serialization behavior.
- Preserve monkeypatch compatibility for `app.routers.pixelle._get_proxy_client`.
- Preserve both exported routers: `router` and `proxy_router`.
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
