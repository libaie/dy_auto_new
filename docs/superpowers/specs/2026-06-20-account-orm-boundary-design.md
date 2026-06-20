# Account ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move the `Account` ORM class body from `app.db_models` into
`app.db.models.account_operations`.

## Design

- `app.db.models.account_operations` owns `Account`.
- `app.db_models.Account` remains a compatibility re-export.
- Account operations domain modules import `Account` from the domain ORM path.

## Out Of Scope

- Do not move `Task`, account groups, chains, channels, devices, or route
  behavior.
- Do not change table names, columns, relationships, response shapes, or
  websocket payloads.

## Verification

- Add an account operations ORM boundary test.
- Run focused account operations boundary/read-model/mutation tests.
