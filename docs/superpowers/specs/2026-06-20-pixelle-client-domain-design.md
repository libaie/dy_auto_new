# Pixelle Client Domain Design

Date: 2026-06-20

## Goal

Move the Pixelle-Video HTTP transport client into the `pixelle_integration`
domain. The client owns Pixelle base URL normalization, API key lookup,
lazy `httpx.AsyncClient` creation, retry behavior, JSON parsing, and shutdown
cleanup.

## Design

`app.domains.pixelle_integration.pixelle_client` becomes the implementation
owner for `DEFAULT_BASE_URL`, `_get_base_url`, `_get_api_key`, `_get_client`,
`_pixelle_request`, and `close_client`.

`app.services.pixelle_client` remains a `sys.modules` compatibility facade so
legacy imports, monkeypatches, and app shutdown keep resolving to the same
module object. Not-yet-moved service modules such as `pixelle_stage_client`
may keep their legacy import until their own migration.

Clean domain callers should import the domain path directly:

- `app.domains.image_generation.image_creation_router`
- `app.domains.script_pipeline.pipeline_router`

## Boundaries

- Keep Pixelle execution orchestration in `app.services.pixelle_execution_service`.
- Keep Pixelle stage client migration out of this slice.
- Preserve retry, non-JSON, 4xx, 5xx, timeout, API key, and no-proxy behavior.
- Preserve `app.services.pixelle_client.close_client` for `app.main` shutdown.

## Verification

- Add a boundary test for domain ownership, legacy facade identity, direct
  domain imports, README registration, and mocked legacy-path request behavior.
- Run existing Pixelle client tests.
- Run app import smoke to catch startup/shutdown import regressions.
