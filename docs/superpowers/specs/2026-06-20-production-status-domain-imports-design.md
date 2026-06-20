# Production Status Domain Imports Design

Date: 2026-06-20

## Goal

Remove remaining domain-owned imports of `app.services.production_status`.
The implementation already lives in
`app.domains.video_production.production_status`; domain modules should import
that path directly.

## Design

Update only the four clean domain modules currently importing the legacy
facade:

- `app.domains.ai_video_series.story_planning`
- `app.domains.ai_video_series.style_lock`
- `app.domains.agency_operations.agency_router`
- `app.domains.creative_library.anchor_service`

Keep `app.services.production_status` as a compatibility facade for tests,
migration docs, and service modules whose owning domains have not moved.

## Verification

Add one boundary test that checks the spec/plan terms, verifies these domain
modules no longer contain `app.services.production_status`, and proves the
legacy facade still resolves to the same module object as the domain
implementation.
