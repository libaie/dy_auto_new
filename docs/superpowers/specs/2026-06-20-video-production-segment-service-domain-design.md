# Video Production Segment Service Domain Design

## Context

`app.services.production_segment_service` currently owns the public `retry_segment`
helper for `/api/video-production/*` retry flows, while the implementation is a
thin delegation to `retry_segment_with_impact`. The helper belongs with the
video production domain because it is only used by the domain router and
production review tests.

## Approved Approach

Move the implementation to
`app.domains.video_production.production_segment_service` and keep
`app.services.production_segment_service` as a temporary compatibility facade.
Update domain-owned imports, including `retry_segment` in
`video_production_router.py`, to use the domain path directly.

## Boundaries

- Preserve `retry_segment(db, segment_id)` behavior and return type.
- Preserve existing callers that import `app.services.production_segment_service`.
- Do not move `retry_segment_with_impact`; retry impact logic remains in
  `app.services.production_retry_service` until that larger service has its own
  migration step.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.production_segment_service`,
  `app.services.production_segment_service`, and `retry_segment`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def retry_segment`.
- Prove the domain router imports the domain helper path directly.
