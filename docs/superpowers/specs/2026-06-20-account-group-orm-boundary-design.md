# Account Group ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move `AccountGroup` and `AccountGroupMember` ORM class bodies from
`app.db_models` into `app.db.models.account_operations`.

## Design

- `app.db.models.account_operations` owns `Account`, `AccountGroup`, and
  `AccountGroupMember`.
- `app.db_models` remains a compatibility re-export surface.
- Account operations domain modules import account group models from the domain
  ORM module.

## Out Of Scope

- Do not move `Task`, chain, channel, device, or route behavior.
- Do not change table names, constraints, relationships, response shapes, or
  websocket payloads.

## Verification

- Extend the account operations ORM boundary test to cover both account group
  models.
- Run focused account operations boundary/read-model/mutation tests.
