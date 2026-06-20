# Account Operations Domain

This domain will own account CRUD, account groups and membership, channels,
channel items, chain templates, and chain instance orchestration metadata.

Device task polling remains in `device_operations`. Content collection and DM
business use cases remain in `content_collection`.

## PR2 Allowed

- Create `server/app/domains/account_operations/__init__.py`.
- Create this README.
- Expose `DOMAIN_NAME = "account_operations"`.
- Expose `PUBLIC_ROUTE_PREFIXES = ("/api/accounts", "/api/account-groups", "/api/channels", "/api/chains")`.
- Document route ownership, facade register, notification payloads, and cleanup gates.

## PR2 Not Allowed

- Do not move route behavior in PR2.
- Do not create `accounts_router.py`, `account_groups_router.py`, `channels_router.py`, or `chains_router.py` in PR2.
- Do not change `/api/accounts/*`, `/api/account-groups/*`, `/api/channels/*`, or `/api/chains/*` paths, methods, auth dependencies, response shapes, or realtime payloads.
- Do not move `server/app/routers/tasks.py` into this domain.
- Do not move device polling, content collection, DM, ORM model ownership, or frontend code.

## PR3 Allowed

- Create `accounts_router.py` from the current `app.routers.accounts` behavior.
- Create `account_groups_router.py` from the current `app.routers.account_groups` behavior.
- Create `channels_router.py` from the current `app.routers.channels` behavior.
- Create `chains_router.py` from the current `app.routers.chains` behavior.
- Replace legacy router files with compatibility facades.
- Keep route paths, methods, auth dependencies, response shapes, and realtime payloads unchanged.

## PR3 Not Allowed

- Do not split handler internals yet.
- Do not change application wiring away from legacy imports yet.
- Do not move `server/app/routers/tasks.py`.
- Do not move device polling or content collection behavior.

## PR4 Allowed

- Move account and account group payload shaping to `read_models.py`.
- Move account CRUD to `account_use_cases.py`.
- Move account group membership behavior to `group_use_cases.py`.
- Move channel CRUD, channel item updates, batch edits, and channel payload shaping to `channel_use_cases.py`.
- Move account, group, and channel websocket helpers to `realtime_events.py`.

## PR4 Not Allowed

- Do not move chain orchestration internals yet.
- Do not change `accounts_changed`, `account_groups_changed`, `channels_changed`, or `new_task_available` payloads.
- Do not move ORM model ownership or persistence class bodies.

## PR5 Allowed

- Move chain template CRUD and chain instance create/list/detail/cancel/retry to `chain_use_cases.py`.
- Keep calls into `chain_service` and `task_service` behind `adapters.py` where needed.
- Preserve `chains_changed` admin broadcasts.
- Preserve direct device cancel payloads from chain cancel paths.

## PR5 Not Allowed

- Do not move device task polling, task result reporting, or device websocket ownership.
- Do not change task-service contracts, chain state transitions, or response shapes.
- Do not move ORM model ownership or persistence class bodies.

## PR6 Allowed

- Inventory production imports of `app.routers.accounts`, `app.routers.account_groups`, `app.routers.channels`, and `app.routers.chains`.
- Move `server/app/main.py` route wiring to `app.domains.account_operations` routers.
- Keep legacy router modules as compatibility facades for old import paths.
- Keep all public paths, methods, auth dependencies, response shapes, and realtime payloads unchanged.

## PR6 Not Allowed

- Do not delete legacy router facades.
- Do not remove router facade tests yet.
- Do not move `server/app/routers/tasks.py`.
- Do not move device, content collection, or DM ownership.

## Ownership Rules

- `app.domains.account_operations` owns the target migration boundary for `/api/accounts/*`, `/api/account-groups/*`, `/api/channels/*`, and `/api/chains/*`.
- `app.routers.accounts` remains the compatibility import path for `/api/accounts/*` callers outside app wiring.
- `app.routers.account_groups` remains the compatibility import path for `/api/account-groups/*` callers outside app wiring.
- `app.routers.channels` remains the compatibility import path for `/api/channels/*` callers outside app wiring.
- `app.routers.chains` remains the compatibility import path for `/api/chains/*` callers outside app wiring.
- `app.domains.account_operations.read_models` owns account, group, member, channel, channel item, chain template, chain instance, and chain task payload shaping.
- `app.domains.account_operations.account_use_cases` owns account CRUD and account status behavior.
- `app.domains.account_operations.group_use_cases` owns account group CRUD and membership add/remove behavior.
- `app.domains.account_operations.channel_use_cases` owns channel CRUD, channel item mutation, batch item edits, and channel status transitions.
- `app.domains.account_operations.channel_service` owns `ChannelService` channel creation, item claim/recovery, quota/risk-control handling, and channel stats.
- `app.domains.account_operations.chain_use_cases` owns chain template CRUD and chain instance create/list/detail/cancel/retry orchestration.
- `app.domains.account_operations.chain_service` owns `ChainService` chain instance orchestration, step task creation, and chain advancement.
- `app.domains.account_operations.realtime_events` owns `accounts_changed`, `account_groups_changed`, `channels_changed`, `chains_changed`, and `new_task_available` websocket helper calls.
- `app.domains.account_operations.adapters` owns narrow adapter calls into current ORM sessions, `channel_service`, `chain_service`, and `task_service`.
- `server/app/routers/tasks.py` remains outside this domain unless a separate task-domain or chain-task adapter plan approves it.
- Domain non-router use-case modules must avoid FastAPI imports unless they are route assembly modules.

## Facade Register

| Facade | Target | Introduced | Exit condition |
|---|---|---|---|
| `app.routers.accounts` | `app.domains.account_operations.accounts_router` | Planned PR3 | Route/auth snapshots and existing account API tests pass with the domain router and all callers have an explicit compatibility path. |
| `app.routers.account_groups` | `app.domains.account_operations.account_groups_router` | Planned PR3 | Account group CRUD and member tests pass with the domain router and all callers have an explicit compatibility path. |
| `app.routers.channels` | `app.domains.account_operations.channels_router` | Planned PR3 | Channel API, edit, model, service, and notification tests pass with the domain router. |
| `app.routers.chains` | `app.domains.account_operations.chains_router` | Planned PR3 | Chain API, chain service, task compatibility, and device cancel notification tests pass with the domain router. |
| `app.services.chain_service` | `app.domains.account_operations.chain_service` | Chain service domain slice | Keep while `rg -n "app\.services\.chain_service" server/app -g "*.py"` returns the approved `task_service` compatibility import; remove only when that command returns no production imports. |
| `app.services.channel_service` | `app.domains.account_operations.channel_service` | Channel service domain slice | Keep while `rg -n "app\.services\.channel_service" server/app -g "*.py"` returns approved task/device bridge compatibility imports; remove only when that command returns no production imports. |

## Migration Checklist

1. Characterize current route/auth snapshots, read-model shapes, and realtime events.
2. Add this metadata-only domain skeleton.
3. Move legacy route behavior behind domain routers with compatibility facades.
4. Split read models, account use cases, group use cases, channel use cases, and realtime helpers into focused modules.
5. Split chain template and chain instance orchestration into focused modules with adapter boundaries.
6. Move app route wiring to domain router imports while keeping legacy facades.
7. Remove compatibility facades only after import inventories and route snapshots prove no behavior drift.

## Test Commands

Run the PR1/PR2 boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_auth_parity.py server/tests/test_account_operations_domain_boundary.py server/tests/test_account_operations_read_models.py server/tests/test_account_operations_notifications.py -q
```

Run the current compatibility checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_accounts_api.py server/tests/test_account_groups_api.py server/tests/test_channel_api.py server/tests/test_channel_edit_api.py server/tests/test_channel_e2e.py server/tests/test_channel_models.py server/tests/test_channel_service.py server/tests/test_chains_api.py server/tests/test_chain_service.py server/tests/test_tasks_api.py server/tests/test_task_service.py -q
```

## Compatibility Cleanup Gates

Do not remove `app.routers.accounts`, `app.routers.account_groups`, `app.routers.channels`, or `app.routers.chains` until all of these are true:

- `rg "app\.routers\.(accounts|account_groups|channels|chains)|from app\.routers import (accounts|account_groups|channels|chains)" server/app server/tests` returns only approved compatibility shims, README entries, and cleanup tests.
- `server/tests/test_account_operations_auth_parity.py` passes against the domain routers.
- `server/tests/test_account_operations_router_facade.py` proves old and new router import paths expose the same route objects during the alias phase.
- `server/tests/test_account_operations_read_models.py` proves response shapes are unchanged.
- `server/tests/test_account_operations_notifications.py` proves websocket payloads still reach admins and devices.
- `app.main` imports account operations routers from `app.domains.account_operations`.
- Release notes mention the import-path migration.
- Do not remove `app.services.chain_service` while `server/app/services/task_service.py` imports it; removal requires zero production matches from `rg -n "app\.services\.chain_service" server/app -g "*.py"`.

Do not move `server/app/routers/tasks.py`, device polling, content collection, DM, ORM model ownership, or persistence class bodies until separate plans approve those boundaries.
