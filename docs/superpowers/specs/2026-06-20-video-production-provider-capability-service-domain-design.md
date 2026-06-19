# Video Production Provider Capability Service Domain Design

Status: auto-approved.

## Context

`app.services.provider_capability_service` defines the real provider capability
defaults, merges provider model configuration into a capability map, and gates
safe real paid execution. It is video-production-specific policy but still lives
in the flat service folder.

## Decision

Move the implementation to
`app.domains.video_production.provider_capability_service` and keep
`app.services.provider_capability_service` as a thin `sys.modules`
compatibility facade.

Existing provider executor, worker, system health, and tests can continue using
the legacy path until those modules are migrated or intentionally approved as
cross-domain consumers.

## Scope

In scope:

- Create `server/app/domains/video_production/provider_capability_service.py`
  with the current implementation.
- Update the moved helper to import
  `app.domains.video_production.production_errors` directly.
- Replace `server/app/services/provider_capability_service.py` with a
  compatibility facade.
- Update `server/app/domains/video_production/README.md` to document capability
  helper ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object.

Out of scope:

- No behavior changes to `DEFAULT_REAL_PROVIDER_CAPABILITY`,
  `capability_from_model_config`, or `assert_real_paid_allowed`.
- No migration of provider executor, production worker, video production
  service, or system health consumers in this step.

## Architecture

The domain provider capability service owns:

- `DEFAULT_REAL_PROVIDER_CAPABILITY`
- `capability_from_model_config`
- `assert_real_paid_allowed`

The legacy service module imports the domain capability module, replaces itself
in `sys.modules`, and updates globals so existing imports and monkeypatches keep
targeting the same module object.

## Error Handling

Existing behavior stays unchanged. Missing real paid execution safety flags
raise `ProductionRepairableError` with `ProductionErrorCode.PROVIDER_SUBMIT_FAILED`.

## Testing

Add `server/tests/test_video_production_provider_capability_service_facade.py`
to verify:

- this spec and plan mention
  `app.domains.video_production.provider_capability_service`,
  `app.services.provider_capability_service`,
  `DEFAULT_REAL_PROVIDER_CAPABILITY`, `capability_from_model_config`,
  `assert_real_paid_allowed`, `ProductionRepairableError`, and
  `ProductionErrorCode`;
- the domain capability service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  constants/functions;
- the moved implementation imports the domain production errors path directly;
- the video production README records capability helper ownership, facade
  mapping, and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_capability_service_facade.py server/tests/test_provider_stage_executor.py -q
```
