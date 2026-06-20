# Quality Audit Gate Domain Design

## Context

`app.services.audit_gate` classifies audit provider responses into production
gate decisions. The logic is specific to quality audit behavior and is consumed
by the quality audit route and video production review flows.

The quality audit route already lives in `app.domains.quality_audit`, but the
gate classifier still lives in the generic services folder.

## Approved Approach

Move the implementation to `app.domains.quality_audit.audit_gate` and keep
`app.services.audit_gate` as a temporary compatibility facade. Update the clean
quality audit router to import the domain classifier directly.

Do not touch `video_production_service.py` in this slice because it has
unrelated work in progress. Its legacy import remains supported by the facade.

## Boundaries

- Preserve `classify_audit_gate` behavior and default `approve_threshold`.
- Preserve error, missing config, low score, and high score gate semantics.
- Preserve existing callers that import `app.services.audit_gate`.
- Document the legacy facade in the quality audit domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.quality_audit.audit_gate`, `app.services.audit_gate`,
  `classify_audit_gate`, and `approve_threshold`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def classify_audit_gate`.
- Prove the quality audit router imports the domain classifier.
- Prove the quality audit README and same-day quality audit design spec name
  the domain gate boundary.
- Run audit gate and quality audit route facade tests after migration.
