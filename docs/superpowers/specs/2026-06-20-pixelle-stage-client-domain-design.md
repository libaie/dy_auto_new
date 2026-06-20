# Pixelle Stage Client Domain Design

Date: 2026-06-20

## Goal

Move the Pixelle stage API helper into the `pixelle_integration` domain. The
helper owns Pixelle stage payload construction for image batch, image create,
stage status, video batch, and compose calls.

## Design

`app.domains.pixelle_integration.pixelle_stage_client` becomes the
implementation owner for `submit_image_batch`, `submit_image_create`,
`get_stage_task`, `submit_video_batch`, and `submit_compose`.

`app.services.pixelle_stage_client` remains a `sys.modules` compatibility
facade so legacy imports and monkeypatches keep resolving to the same module
object. Existing legacy orchestration services may keep their import until
their own domain migration.

The domain implementation imports `_pixelle_request` from
`app.domains.pixelle_integration.pixelle_client`.

## Boundaries

- Keep Pixelle HTTP transport ownership in `pixelle_client.py`.
- Keep video production orchestration outside this slice.
- Keep image creation orchestration outside this slice.
- Preserve all payload keys, validation errors, paths, and monkeypatch
  behavior.

## Verification

- Add a boundary test for domain ownership, legacy facade identity, direct
  domain client import, README registration, and legacy monkeypatch behavior.
- Run existing Pixelle stage client tests.
- Run focused callers that use the stage client.
- Run app import smoke to catch startup import regressions.
