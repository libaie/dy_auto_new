# Production Observability Domain Design

## Context

`app.services.production_observability` writes `ProductionAuditEvent` rows and
redacts secret-like payload keys recursively. It is used by video production,
image generation, and agency operations, so it is not owned by any one feature
domain.

## Approved Approach

Create shared domain package `app.domains.production_observability` and move the
implementation to
`app.domains.production_observability.production_observability_service`.
Keep `app.services.production_observability` as a temporary compatibility
facade.

Update only clean domain callers in this slice:

- `app.domains.agency_operations.agency_router`
- `app.domains.image_generation.image_ab_test_service`
- `app.domains.image_generation.image_production_strategy_service`
- `app.domains.video_production.production_gate_evaluator`
- `app.domains.video_production.mock_scale_scheduler_service`
- `app.domains.video_production.provider_stage_executor`

Leave WIP service callers on the legacy path for now; the facade preserves
their behavior.

## Boundaries

- Preserve `SECRET_KEYS`, `_normalize_key`, `_redact`, and
  `record_production_event` behavior.
- Preserve the caller-owned transaction boundary: `record_production_event`
  flushes but does not commit.
- Preserve secret redaction for nested dictionaries and lists.
- Preserve existing callers that import `app.services.production_observability`.
- Document the legacy facade and cleanup gate in the shared domain README.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.production_observability.production_observability_service`,
  `app.services.production_observability`, `_redact`, and
  `record_production_event`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def record_production_event`.
- Prove clean domain callers import the shared domain path directly.
- Prove the shared domain README registers the facade and cleanup gate.
- Run focused observability behavior tests after migration.
