# Quality Audit Domain Design

## Goal

Move the legacy `/api/audit/*` image-quality audit router into a business-domain
package without changing HTTP behavior, audit payloads, provider call shapes,
report persistence, or monkeypatch compatibility.

## Approved Approach

Use the established facade-first migration pattern:

1. Create `app.domains.quality_audit`.
2. Move the current `app.routers.audit` implementation to
   `app.domains.quality_audit.audit_router` in `audit_router.py`.
3. Replace `app.routers.audit` with a thin `sys.modules` compatibility facade
   pointing at the domain router module.
4. Wire `app.main` directly to `audit_router.router`.
5. Update production service imports of `_do_audit` to use the domain module.

## Ownership Boundary

`app.domains.quality_audit` owns:

- `POST /api/audit/image`
- `GET /api/audit/reports/{target_type}/{target_id}`
- `AuditImageRequest`
- Audit model resolution wrapper `_get_audit_model`
- Provider execution helpers `_do_audit`, `_audit_openai_compatible`, and
  `_audit_gemini`
- Audit payload helpers such as `_audit_user_content`, `_audit_config`, and
  `_supports_vision_audit`
- JSON response parsing and `AuditReport` persistence inside the route

`app.domains.quality_audit` does not own:

- `AuditReport` and `AIModel` ORM definitions, which remain in `app.db_models`.
- DB session construction, which remains in `app.database`.
- Auth dependencies, which remain in `app.deps`.
- Audit gate classification through `classify_audit_gate` now lives in
  `app.domains.quality_audit.audit_gate`; `app.services.audit_gate` remains as
  a temporary compatibility facade.
- Model registry and runtime model configuration.
- Video production orchestration, which only consumes `_do_audit`.

## Compatibility Contract

The migration must preserve:

- Route paths, methods, names, dependency names, and response shapes.
- Current behavior where `GET /api/audit/reports/{target_type}/{target_id}`
  depends only on `get_db`.
- OpenAI-compatible/Bailian text-only audit payload behavior.
- Vision-enabled OpenAI `image_url` payload behavior.
- Gemini audit payload behavior.
- `app.routers.audit._do_audit` monkeypatch compatibility for existing tests.
- `app.routers.audit.httpx.post` monkeypatch compatibility.

## Testing Strategy

Add boundary tests that fail before the move and pass after domain wiring:

- Spec and plan mention the domain, facade, routes, `AuditReport`,
  `AuditImageRequest`, and `_do_audit`.
- Domain package exports `DOMAIN_NAME` and `PUBLIC_ROUTE_PREFIX`.
- Domain README documents facade and cleanup gates.
- Legacy `app.routers.audit` is a thin `sys.modules` facade.
- Legacy and domain imports resolve to the same module object.
- Router snapshot matches the two existing `/api/audit/*` routes.
- FastAPI route table uses `app.domains.quality_audit.audit_router` endpoint
  modules.
- `video_production_service.py` imports `_do_audit` from the domain, not the
  legacy router path.

Run existing audit payload and video-production audit-gate tests after
migration.

## Cleanup Gates

Do not remove `app.routers.audit` until all of these are true:

- `app.main` imports `audit_router` from `app.domains.quality_audit`.
- Production service imports use `app.domains.quality_audit.audit_router`.
- Route/auth snapshots pass against the domain endpoint module.
- Existing audit payload and video-production audit-gate tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.audit`.
- Tests that monkeypatch the legacy module path are either updated or
  intentionally kept compatible through the alias phase.
