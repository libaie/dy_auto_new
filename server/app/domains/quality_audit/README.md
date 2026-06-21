# Quality Audit Domain

This domain owns AI-assisted image and video asset quality audit routes.

## Owned Routes

- `/api/audit/*`

## Not Owned

- `AuditReport` ORM model definition lives in `app.db.models.quality_audit`.
- `AIModel` ORM model definition lives in
  `app.db.models.model_configuration`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Model registry and runtime model configuration stay in shared services.
- Video production orchestration stays in
  `app.domains.video_production.video_production_service`.

## Current Modules

- `audit_router.py` owns `AuditImageRequest`, `/api/audit/*` route handlers,
  provider audit calls, `_do_audit`, `_audit_openai_compatible`,
  `_audit_gemini`, payload helpers, JSON parsing, and `AuditReport`
  persistence inside the route.
- `app.db.models.quality_audit` owns the `AuditReport` ORM class body.
- `audit_gate.py` owns `classify_audit_gate` for mapping provider audit
  responses into quality gate decisions.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve current report-listing dependency behavior.
- Keep video production as a consumer of `_do_audit`, not an owner of audit
  route behavior.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
