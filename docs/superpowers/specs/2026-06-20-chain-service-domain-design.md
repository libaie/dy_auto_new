# Chain Service Domain Design

Date: 2026-06-20

## Goal

Move chain orchestration internals from `app.services.chain_service` into
`app.domains.account_operations.chain_service` without changing chain template,
chain instance, task advancement, websocket push, or task reporting behavior.

## Approved Approach

Move `server/app/services/chain_service.py` to
`server/app/domains/account_operations/chain_service.py`.

Keep `app.services.chain_service` as a `sys.modules` compatibility facade.
`account_operations.adapters` imports the domain service directly. `task_service`
keeps the legacy import path until task ownership gets its own slice.

## Boundaries

- Preserve `ChainService`, `chain_service`, `_account_lock`,
  `VALID_STEP_TYPES`, and `_task_to_push_dict`.
- Preserve account busy checks, group expansion, chain instance creation,
  step task creation, task advancement, completion/failure transitions, and
  websocket push scheduling.
- Preserve `task_service.report_result` behavior through the legacy import.
- Do not move `task_service`, device polling, route behavior, ORM models,
  websocket manager ownership, or chain API response shaping in this slice.

## Target Structure

```text
server/app/domains/account_operations/
  chain_service.py
  adapters.py

server/app/services/
  chain_service.py  # compatibility facade
```

## Verification

- Add a boundary test proving this spec and plan mention the domain module,
  legacy facade, and `ChainService`.
- Prove the domain file exists and the legacy file is a thin facade.
- Prove legacy and domain imports resolve to the same module object.
- Prove `account_operations.adapters` imports the domain service directly.
- Prove `task_service` stays on the legacy import path.
- Run chain service, chains API, tasks API, and account operations boundary
  tests after migration.
