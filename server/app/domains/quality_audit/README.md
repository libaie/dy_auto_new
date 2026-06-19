# Quality Audit Domain

This domain owns AI-assisted image and video asset quality audit routes.

## Owned Routes

- `/api/audit/*`

## Not Owned

- `AuditReport` and `AIModel` ORM model definitions stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Audit gate classification stays in `app.services.audit_gate`.
- Model registry and runtime model configuration stay in shared services.
- Video production orchestration stays in `app.services.video_production_service`.

## Current Modules

- `audit_router.py` owns `AuditImageRequest`, `/api/audit/*` route handlers,
  provider audit calls, `_do_audit`, `_audit_openai_compatible`,
  `_audit_gemini`, payload helpers, JSON parsing, and `AuditReport`
  persistence inside the route.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.audit` | `app.domains.quality_audit.audit_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve current report-listing dependency behavior.
- Preserve monkeypatch compatibility for `app.routers.audit._do_audit` and
  `app.routers.audit.httpx.post`.
- Keep video production as a consumer of `_do_audit`, not an owner of audit
  route behavior.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `audit_router` from `app.domains.quality_audit`.
- Production consumers import `_do_audit` from
  `app.domains.quality_audit.audit_router`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing audit payload and video production audit-gate tests pass.
- Import inventory shows no unapproved production imports of `app.routers.audit`.
