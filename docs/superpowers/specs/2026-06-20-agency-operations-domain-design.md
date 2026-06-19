# Agency Operations Domain Design

Status: auto-approved.

## Goal

Move the `/api/agency/*` HTTP surface out of the flat `app.routers` layer into
`app.domains.agency_operations` without changing route paths, auth dependencies,
response shapes, or monkeypatch compatibility.

## Domain Boundary

The new domain owns:

- `app.domains.agency_operations.agency_router`
- `agency_router.py`
- `/api/agency/experts`
- `/api/agency/invocations`
- `/api/agency/creative-patches`
- `/api/agency/assets/{asset_id}/multimodal-review`
- `/api/agency/repair-tasks`

The router continues to use shared services and models:

- `AgencyExpertInvocation`
- `AgencyCreativePatch`
- `ProductionJob`
- `ProductionAuditEvent`
- `app.services.agency_manifest`
- `app.services.agency_creative_patch_service`
- `app.services.provider_cost_reservation_service`

## Compatibility

Keep `app.routers.agency` as a thin facade that aliases to
`app.domains.agency_operations.agency_router` through `sys.modules`. Existing
imports and test monkeypatches must see the same module object during the
transition.

## Security And Behavior

- Preserve `verify_admin_token` on `/experts`.
- Preserve `require_role("admin")` on detail, invocation, creative patch,
  multimodal review, and repair task endpoints.
- Preserve secret redaction through `_redact_model_config_snapshot`.
- Preserve paid repair retry budget and reservation checks.
- Preserve repair task state transitions and audit event creation.

## Exit Criteria

- `app.main` imports `agency_router` from `app.domains.agency_operations`.
- `app.main` includes `agency_router.router`, not `agency.router`.
- Route/auth snapshots show endpoint modules under
  `app.domains.agency_operations.agency_router`.
- `app.routers.agency` remains a <=20 line facade with no `APIRouter`.
- Focused agency API, console, repair, and runtime tests pass.
