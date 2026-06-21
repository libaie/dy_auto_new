# Pixelle Integration Domain

This domain owns the Pixelle-Video configuration bridge and transparent proxy
routes.

## Owned Routes

- `/api/pixelle/*`
- `/api/pixelle-proxy/*`

## Not Owned

- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Runtime model resolution stays in shared services.
- Video production orchestration stays outside this domain.
- Video production orchestration stays in its own router and services.

## Current Modules

- `pixelle_router.py` owns `PixelleConfigUpdate`, `router`, `proxy_router`,
  `_serialize_ai_models`, `_redact_secrets`, `_get_proxy_client`,
  `_pixelle_headers`, config bridge read/write helpers, template preview
  serving, test-connection handling, and transparent proxy forwarding.
- `pixelle_client.py` owns `DEFAULT_BASE_URL`, Pixelle base URL/API key lookup,
  lazy `httpx.AsyncClient`, `_pixelle_request`, retries, JSON parsing, and
  `close_client`.
- `pixelle_stage_client.py` owns Pixelle stage payload construction for image
  batch, image create, stage status, video batch, and compose calls:
  `submit_image_batch`, `submit_image_create`, `get_stage_task`,
  `submit_video_batch`, and `submit_compose`.
- `pixelle_execution_service.py` owns `build_video_stage_frame` payload mapping
  for Pixelle video stage segment frames.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve recursive secret redaction and model serialization behavior.
- Preserve both exported routers: `router` and `proxy_router`.
- Keep video-library and video-production ownership outside this domain.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
