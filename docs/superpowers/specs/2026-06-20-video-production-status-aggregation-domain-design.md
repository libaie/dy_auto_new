# Video Production Status Aggregation Domain Design

## Context

`app.services.production_status_aggregation` owns the parent-status rollup for
production segment changes. It recalculates shot, scene, episode, and plan
statuses after a segment changes. That behavior is part of the video production
control plane, but the module still lives in the generic service folder.

## Approved Approach

Move the implementation to
`app.domains.video_production.production_status_aggregation` and keep
`app.services.production_status_aggregation` as a temporary compatibility
facade. Do not edit `video_production_service.py` in this step because that
file has unrelated work in progress; its legacy import remains an approved
service-module consumer until the service itself is migrated.

## Boundaries

- Preserve `_parent_status(child_statuses)` ordering and fallback semantics.
- Preserve `recompute_from_segment(db, segment_id)` behavior and database
  commit behavior.
- Preserve existing callers that import
  `app.services.production_status_aggregation`.
- Do not move production ORM models.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.production_status_aggregation`,
  `app.services.production_status_aggregation`, `_parent_status`, and
  `recompute_from_segment`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def recompute_from_segment`.
- Run the pause/resume status aggregation behavior test after the migration.
