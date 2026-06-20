# Video Production Provider Stage Executor Domain Design

## Context

`app.services.provider_stage_executor` owns the real provider two-phase submit
and sync boundary. It coordinates provider capability checks, cost reservations,
provider stage tasks, state transitions, queue retry handoff, and production
audit events.

The executor is part of the video production control plane, but it still lives
in the generic services folder. Several of its helper dependencies have already
moved into `app.domains.video_production`.

## Approved Approach

Move the implementation to
`app.domains.video_production.provider_stage_executor` and keep
`app.services.provider_stage_executor` as a temporary compatibility facade.
Update clean domain callers that only read executor constants, such as the
system health router, to import the domain path directly.

Do not touch `production_worker_service.py` in this slice because it has
unrelated work in progress. Its legacy import remains supported by the facade.

Inside the moved module, import already-migrated helpers from
`app.domains.video_production` and shared audit helpers from
`app.domains.production_observability`. Keep `production_queue_service` on the
legacy service path for now because it has not been migrated in this slice.

## Boundaries

- Preserve `ProviderStageExecutor`, `PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT`,
  `PROVIDER_SUBMIT_WORKER_COUNT_ENV`, and
  `assert_paid_submit_deployment_safe`.
- Preserve process-local throttle behavior and the existing deployment
  contract.
- Preserve cost reservation, provider task, and queue retry behavior.
- Preserve existing callers that import `app.services.provider_stage_executor`.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.provider_stage_executor`,
  `app.services.provider_stage_executor`, `ProviderStageExecutor`, and
  `PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `class ProviderStageExecutor`.
- Prove the moved executor imports already-migrated helper contracts from the
  video production domain.
- Prove the system health router uses the domain executor path for
  `PROVIDER_SUBMIT_WORKER_COUNT_ENV`.
- Run provider executor and throttle behavior tests after migration.
