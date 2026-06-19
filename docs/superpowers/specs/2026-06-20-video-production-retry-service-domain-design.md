# Video Production Retry Service Domain Design

## Context

`app.services.production_retry_service` owns retry impact calculation and retry
version creation for production segments. It is used by the video production
router and by the domain `production_segment_service`, so keeping it in the
generic service folder leaves a video-production-specific workflow outside the
business domain.

## Approved Approach

Move the implementation to
`app.domains.video_production.production_retry_service` and keep
`app.services.production_retry_service` as a temporary compatibility facade.
Update domain-owned callers to import the retry helper from the domain path
directly:

- `app.domains.video_production.production_segment_service`
- `app.domains.video_production.video_production_router`

`app.services.production_queue_service` remains in the service layer for now
because queue orchestration is a larger module with separate migration risk.

## Boundaries

- Preserve `get_retry_impact(db, segment_id)` response shape.
- Preserve `retry_segment_with_impact(db, segment_id)` versioning, asset
  demotion, enqueue, and run status update behavior.
- Preserve `_enqueue_retry_stage_job`, `_run_for_segment`, and
  `_retry_stage_for_segment` semantics.
- Preserve existing callers that import `app.services.production_retry_service`.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.production_retry_service`,
  `app.services.production_retry_service`, `get_retry_impact`, and
  `retry_segment_with_impact`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def get_retry_impact`.
- Prove domain-owned callers import the retry helper from the domain path.
- Run retry impact and retry segment behavior tests after migration.
