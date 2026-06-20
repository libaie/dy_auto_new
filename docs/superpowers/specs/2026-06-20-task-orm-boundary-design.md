# Task ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move the `Task` ORM class body from `app.db_models` into
`app.db.models.task_operations`.

## Design

- `app.db.models.task_operations` owns the `tasks` persistence model.
- `app.db_models` remains the compatibility re-export surface for existing
  imports, tests, and Alembic-style metadata collection.
- The task operations owner domain imports `Task` from the domain ORM module.

## Out Of Scope

- Do not move device polling, device reporting, chain orchestration, channel
  execution behavior, or task API response shapes.
- Do not change table names, columns, relationships, defaults, indexes, or
  task leasing semantics.
- Do not migrate non-owner domains away from `app.db_models` in this slice.

## Verification

- Add a focused ORM boundary test proving the new module exports the same
  `Task` class as `app.db_models`.
- Run focused task operations boundary and service tests.
- Confirm task operations no longer imports `Task` from `app.db_models`.
