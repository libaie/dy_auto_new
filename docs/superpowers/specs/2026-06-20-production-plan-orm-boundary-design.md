# Production Plan ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move `ProductionPlan` from `app.db_models` into
`app.db.models.video_production`.

## Design

- `app.db.models.video_production` owns the `production_plans` persistence
  model.
- `app.db_models` remains the compatibility re-export surface.
- Video production owner-domain modules import `ProductionPlan` from the
  domain ORM module.

## Out Of Scope

- Do not move production plan versions, episodes, scenes, shots, segments,
  jobs, provider tasks, cost events, assets, runs, or reviews.
- Do not change table names, columns, defaults, indexes, API responses, or
  production behavior.

## Verification

- Extend the existing video production ORM boundary test to prove
  `ProductionPlan` is owned by `app.db.models.video_production`.
- Run focused video production ORM and plan-service tests.
- Confirm video production owner-domain code no longer imports
  `ProductionPlan` from `app.db_models`.
