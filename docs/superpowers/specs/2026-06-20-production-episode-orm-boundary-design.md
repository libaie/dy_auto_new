# Production Episode ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move `ProductionEpisode` from `app.db_models` into
`app.db.models.video_production`.

## Design

- `app.db.models.video_production` owns the `production_episodes` persistence
  model alongside `ProductionPlan` and `ProductionPlanVersion`.
- `app.db_models` remains the compatibility re-export surface.
- Video production owner-domain modules import `ProductionEpisode` from the
  domain ORM module.

## Out Of Scope

- Do not move production scenes, shots, segments, jobs, provider tasks, cost
  events, assets, runs, or reviews.
- Do not change table names, columns, defaults, indexes, API responses, or
  production behavior.

## Verification

- Extend the existing video production ORM boundary test to prove
  `ProductionEpisode` is owned by `app.db.models.video_production`.
- Run focused video production ORM and plan-service tests.
- Confirm video production owner-domain code no longer imports
  `ProductionEpisode` from `app.db_models`.
