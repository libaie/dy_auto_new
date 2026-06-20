# Channel ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move `Channel` and `ChannelItem` ORM class bodies from `app.db_models` into
`app.db.models.account_operations`.

## Design

- `app.db.models.account_operations` owns account, account group, chain, and
  channel metadata models.
- `app.db_models` remains a compatibility re-export surface.
- Account operations modules import channel models from the domain ORM module.

## Out Of Scope

- Do not move `Task`, device, task domain code, or channel execution behavior.
- Do not change table names, indexes, relationships, response shapes, or
  websocket payloads.

## Verification

- Extend the account operations ORM boundary test to cover both channel models.
- Run focused account operations ORM/domain/read-model/mutation tests.
