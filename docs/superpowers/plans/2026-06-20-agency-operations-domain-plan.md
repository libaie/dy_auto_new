# Agency Operations Domain Plan

Status: auto-approved.

## Success Criteria

Agency HTTP behavior is unchanged while ownership moves from `app.routers.agency`
to `app.domains.agency_operations.agency_router`.

## Steps

1. Add automated boundary tests.
   Verify: spec/plan mention `app.domains.agency_operations`, `agency_router.py`,
   `app.routers.agency`, `/api/agency`, `AgencyExpertInvocation`,
   `AgencyCreativePatch`, `_redact_model_config_snapshot`, `repair-tasks`, and
   `multimodal-review`.

2. Add legacy facade compatibility tests.
   Verify: importing `app.routers.agency` and
   `app.domains.agency_operations.agency_router` returns the same module object
   and the router exposes the same `/api/agency/*` route table.

3. Add route/auth parity tests.
   Verify: all `/api/agency/*` routes keep their methods, names, dependency
   names, and move endpoint modules to
   `app.domains.agency_operations.agency_router`.

4. Move router implementation.
   Verify: create `app.domains.agency_operations`, move the current router into
   `agency_router.py`, and replace `app.routers.agency` with a `sys.modules`
   facade.

5. Wire the app directly to the domain.
   Verify: `app.main` imports `agency_router` and includes
   `agency_router.router`; no direct `agency.router` include remains.

6. Run focused regression.
   Verify: new domain tests plus existing agency API, console, repair, and
   runtime tests pass before committing.
