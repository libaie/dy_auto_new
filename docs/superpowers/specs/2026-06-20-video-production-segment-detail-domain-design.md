# Video Production Segment Detail Domain Design

## Context

`app.services.production_segment_detail_service` builds the response payload for
`GET /api/video-production/segments/{segment_id}/detail`. It reads the segment
path, latest assets, asset history, review records, and allowed retry action.
That response is a video production route concern, so the implementation should
live with the video production domain.

## Approved Approach

Move the implementation to
`app.domains.video_production.production_segment_detail_service`, keep
`app.services.production_segment_detail_service` as a temporary compatibility
facade, and update the domain router's local import to use the domain path
directly.

## Boundaries

- Preserve `_asset_payload(asset)` response shape.
- Preserve `get_segment_detail(db, segment_id, history_limit)` behavior,
  including `ValueError("Production segment not found")`.
- Preserve `allowed_actions` returning `["retry"]` for failed retryable segment
  statuses and `[]` otherwise.
- Preserve existing callers that import
  `app.services.production_segment_detail_service`.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.production_segment_detail_service`,
  `app.services.production_segment_detail_service`, `_asset_payload`, and
  `get_segment_detail`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def get_segment_detail`.
- Prove `video_production_router.py` imports the segment detail helper from the
  domain path.
- Run the segment detail API test after the migration.
