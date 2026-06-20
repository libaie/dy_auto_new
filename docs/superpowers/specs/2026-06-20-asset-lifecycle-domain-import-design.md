# Asset Lifecycle Domain Import Design

Date: 2026-06-20

## Goal

Remove the `ai_video_series` domain import of the legacy
`app.services.asset_lifecycle_service` facade.

## Design

`app.domains.ai_video_series.router` should import asset lifecycle helpers from
`app.domains.creative_library.asset_lifecycle_service`.

Keep `app.services.asset_lifecycle_service` as a compatibility facade for
tests and service modules whose owning domains have not moved.

## Verification

Add one boundary test that proves the series domain router uses the direct
creative-library domain import and the legacy facade still resolves to the
same module object as the domain implementation.
