# Video Production Gate Evaluator Domain Design

## Context

`app.services.production_gate_evaluator` evaluates whether image, video, and
compose stages can advance based on latest approved and persisted assets. This
is video-production-specific gate logic, but it currently lives in the generic
service folder.

## Approved Approach

Move the implementation to
`app.domains.video_production.production_gate_evaluator` and keep
`app.services.production_gate_evaluator` as a temporary compatibility facade.
Update the moved module to import `production_segment_frame_ids` from
`app.domains.video_production.video_production_state`. The later production
observability domain migration supersedes the original legacy import note:
`record_production_event` now comes from
`app.domains.production_observability.production_observability_service`.

## Boundaries

- Preserve `STAGE_ASSET_TYPES` and `_asset_type_for_stage` behavior.
- Preserve `_required_ids`, `_latest_assets_by_required_id`,
  `_blocked_reason`, and `evaluate_stage_gate` response shape.
- Preserve audit event recording via `record_production_event`.
- Preserve existing callers that import `app.services.production_gate_evaluator`.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.production_gate_evaluator`,
  `app.services.production_gate_evaluator`, `evaluate_stage_gate`, and
  `STAGE_ASSET_TYPES`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def evaluate_stage_gate`.
- Prove the moved gate evaluator imports the state helper from the domain path.
- Run production gate evaluator behavior tests after migration.
