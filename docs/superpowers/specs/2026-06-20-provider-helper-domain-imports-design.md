# Provider Helper Domain Imports Design

Date: 2026-06-20

## Goal

Remove the remaining domain-owned imports of provider helper service facades.
The implementations already live in the video production domain.

## Design

Update only these clean domain modules:

- `app.domains.agency_operations.agency_router` imports
  `active_reserved_cost` from
  `app.domains.video_production.provider_cost_reservation_service`.
- `app.domains.system_operations.system_health_router` imports
  `capability_from_model_config` from
  `app.domains.video_production.provider_capability_service`.

Keep `app.services.provider_cost_reservation_service` and
`app.services.provider_capability_service` as compatibility facades.

## Verification

Add one boundary test that proves both domain modules use direct domain imports
and both legacy facades still resolve to the same module objects as the domain
implementations.
