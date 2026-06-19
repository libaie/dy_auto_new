# Image Generation A/B Test Service Domain Design

Status: auto-approved.

## Context

The image generation domain owns the image production router, but all A/B group
preview, creation, refresh, winner recommendation, adoption, no-winner decision,
and serialization logic still lives in `app.services.image_ab_test_service`.
This is one of the last large image production services still imported by the
domain router.

## Decision

Move the implementation to
`app.domains.image_generation.image_ab_test_service` and keep
`app.services.image_ab_test_service` as a thin `sys.modules` compatibility
facade.

The moved service should import already-migrated collaborators from domain
paths: image metrics, image recommendation, and selection preview. It should
continue to import image creation and production observability from existing
service paths until those modules have their own migration plans.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_ab_test_service.py` with the
  current implementation.
- Replace `server/app/services/image_ab_test_service.py` with a compatibility
  facade.
- Update the moved A/B service to import domain metrics, domain recommendation,
  and domain selection preview modules.
- Update `server/app/domains/image_generation/image_production_router.py` to
  import A/B helpers from the domain path.
- Update `server/app/domains/image_generation/README.md` to document A/B service
  ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new A/B service imports resolve to
  the same module object.

Out of scope:

- No behavior changes to preview request hashing, idempotency, strategy attempt
  creation, preview validation, cost confirmation, partial failure recording,
  stale group recovery, refresh status transitions, winner/no-winner decisions,
  or audit events.
- No cleanup of legacy imports in existing A/B service or API tests in this
  step.

## Architecture

The domain A/B service owns:

- `preview_ab_group`
- `create_ab_group`
- `refresh_ab_group`
- `recommend_ab_winner`
- `adopt_ab_winner`
- `mark_ab_no_winner`
- `serialize_ab_group`
- A/B request hash, idempotency, and evidence helpers.

The legacy service module imports the domain A/B service module, replaces itself
in `sys.modules`, and updates globals so existing imports and monkeypatches keep
targeting the same module object.

## Data Flow

The image production router calls the domain A/B service. The service still
loads strategies, previews per-strategy selection results, creates image tasks,
tracks attempts/groups, refreshes metrics, and records production audit events
through the same database session and helper calls.

## Error Handling

Error behavior is unchanged. Existing image errors, HTTP exceptions, retryable
flags, affected IDs, and rescue actions must remain byte-for-byte compatible at
the response boundary.

## Testing

Add `server/tests/test_image_generation_ab_test_service_facade.py` to verify:

- this spec and plan mention
  `app.domains.image_generation.image_ab_test_service`,
  `app.services.image_ab_test_service`, `preview_ab_group`,
  `create_ab_group`, `refresh_ab_group`, `recommend_ab_winner`,
  `adopt_ab_winner`, `mark_ab_no_winner`, and `serialize_ab_group`;
- the domain A/B service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical
  key functions/constants;
- the moved domain A/B service imports domain metrics, recommendation, and
  selection preview paths;
- the domain image production router imports the domain A/B service path;
- the image generation README records A/B service ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_ab_test_service_facade.py server/tests/test_image_ab_service.py server/tests/test_image_ab_api.py -q
```
