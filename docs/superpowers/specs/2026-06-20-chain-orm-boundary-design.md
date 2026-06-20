# Chain ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move `ChainTemplate` and `ChainInstance` ORM class bodies from
`app.db_models` into `app.db.models.account_operations`.

## Design

- `app.db.models.account_operations` owns account, account group, and chain
  metadata models.
- `app.db_models` remains a compatibility re-export surface.
- Account operations chain modules import chain models from the domain ORM
  module.

## Out Of Scope

- Do not move `Task`, channel models, devices, or chain execution behavior.
- Do not change table names, columns, relationships, response shapes, or
  websocket payloads.

## Verification

- Extend the account operations ORM boundary test to cover both chain models.
- Run focused account operations ORM/domain/read-model/chain tests.
