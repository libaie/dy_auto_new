# Account Operations Domain Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move account, account group, channel, and task-chain ownership into an account operations domain after device/content dependencies are explicit.

**Architecture:** Keep existing API routes stable, add boundary tests, introduce `app.domains.account_operations`, then move account/group/channel/task-chain use cases behind compatibility facades. This plan owns account administration and orchestration metadata; it must not absorb device task polling or content collection behavior that belongs to the `device_operations` and `content_collection` child domains.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pytest, existing account, account group, channel, and chain services.

---

## First Tasks

- [ ] Characterize account/account-group/channel/chain routes and auth dependencies.
- [ ] Create `server/app/domains/account_operations`.
- [ ] Move route modules through compatibility aliases.
- [ ] Split orchestration use cases from read models.
- [ ] Add cleanup gates for legacy imports.

## File Map

### New Domain Files

- `server/app/domains/account_operations/__init__.py`
  - Exports `DOMAIN_NAME = "account_operations"` and route prefixes `("/api/accounts", "/api/account-groups", "/api/channels", "/api/chains")`.
- `server/app/domains/account_operations/README.md`
  - Facade register, ownership boundaries, route/auth snapshots, cleanup gates, and verification commands.
- `server/app/domains/account_operations/accounts_router.py`
  - Owns `/api/accounts/*` route assembly after the compatibility move.
- `server/app/domains/account_operations/account_groups_router.py`
  - Owns `/api/account-groups/*` route assembly after the compatibility move.
- `server/app/domains/account_operations/channels_router.py`
  - Owns `/api/channels/*` route assembly after the compatibility move.
- `server/app/domains/account_operations/chains_router.py`
  - Owns `/api/chains/*` route assembly after the compatibility move.
- `server/app/domains/account_operations/schemas.py`
  - Owns request/response models currently embedded in account, group, channel, and chain routers.
- `server/app/domains/account_operations/read_models.py`
  - Owns account, group member, channel item, chain template, and chain instance payload shaping.
- `server/app/domains/account_operations/account_use_cases.py`
  - Owns account CRUD and account status operations.
- `server/app/domains/account_operations/group_use_cases.py`
  - Owns account group CRUD and membership add/remove behavior.
- `server/app/domains/account_operations/channel_use_cases.py`
  - Owns channel CRUD, item ordering, batch updates, and channel item mutation behavior.
- `server/app/domains/account_operations/chain_use_cases.py`
  - Owns chain template CRUD, chain instance creation/list/detail/cancel/retry orchestration, and task-service adapter boundaries.
- `server/app/domains/account_operations/realtime_events.py`
  - Owns websocket/admin/device notification helpers for account, group, channel, and chain mutations, preserving existing broadcast and device-send payloads.
- `server/app/domains/account_operations/adapters.py`
  - Narrow adapter layer over current ORM/session access, `channel_service`, `chain_service`, and `task_service`.

### Compatibility Facades To Modify In Future PRs

- `server/app/routers/accounts.py`
  - Becomes a compatibility alias to `app.domains.account_operations.accounts_router`.
- `server/app/routers/account_groups.py`
  - Becomes a compatibility alias to `app.domains.account_operations.account_groups_router`.
- `server/app/routers/channels.py`
  - Becomes a compatibility alias to `app.domains.account_operations.channels_router`.
- `server/app/routers/chains.py`
  - Becomes a compatibility alias to `app.domains.account_operations.chains_router`.
- `server/app/routers/tasks.py`
  - Stays outside this domain unless a PR explicitly moves only chain-owned task orchestration adapters. Device task polling remains out of scope.
- `server/app/main.py`
  - Keeps public route registration stable while imports migrate.

### New Tests

- `server/tests/test_account_operations_auth_parity.py`
  - Snapshots `/api/accounts/*`, `/api/account-groups/*`, `/api/channels/*`, and `/api/chains/*` route methods and dependencies.
- `server/tests/test_account_operations_domain_boundary.py`
  - Verifies domain package metadata, README facade register, app import smoke, and no behavior move in PR1.
- `server/tests/test_account_operations_router_facade.py`
  - Proves old router imports and new domain router imports resolve to the same module objects during migration.
- `server/tests/test_account_operations_read_models.py`
  - Covers list/detail payload shaping for accounts, groups, members, channels, channel items, templates, and instances.
- `server/tests/test_account_operations_mutations.py`
  - Covers account CRUD, group membership, channel item mutation, chain template mutation, auth-sensitive admin actions, and admin websocket mutation broadcasts.
- `server/tests/test_account_operations_chain_orchestration.py`
  - Covers chain instance create/list/detail/cancel/retry, adapter calls into `task_service` or `chain_service`, chain broadcasts, and device send notifications.
- `server/tests/test_account_operations_notifications.py`
  - Patches/asserts `pair_ws_manager.broadcast_to_admins` and `pair_ws_manager.send_to_device` for `accounts_changed`, `account_groups_changed`, `channels_changed`, `chains_changed`, `new_task_available`, and chain cancel/retry device notifications.

### Existing Tests To Keep Green

- `server/tests/test_accounts_api.py`
- `server/tests/test_account_groups_api.py`
- `server/tests/test_channel_api.py`
- `server/tests/test_channel_edit_api.py`
- `server/tests/test_channel_e2e.py`
- `server/tests/test_channel_models.py`
- `server/tests/test_channel_service.py`
- `server/tests/test_chains_api.py`
- `server/tests/test_chain_service.py`
- `server/tests/test_tasks_api.py`
- `server/tests/test_task_service.py`

## PR Sequence

### PR1: Route/Auth And Ownership Characterization

- [ ] Add route/auth snapshots for `/api/accounts/*`, `/api/account-groups/*`, `/api/channels/*`, and `/api/chains/*`.
- [ ] Document which routes use `verify_admin_token` and which create routes use role requirements.
- [ ] Add baseline read-model response tests for account lists, group members, channel items, chain templates, and chain instances.
- [ ] Add notification characterization that patches `pair_ws_manager.broadcast_to_admins` and `pair_ws_manager.send_to_device` around current mutation routes.
- [ ] Confirm `tasks.py` remains outside the route move unless a chain orchestration adapter needs explicit coverage.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_auth_parity.py server/tests/test_account_operations_domain_boundary.py server/tests/test_account_operations_read_models.py server/tests/test_account_operations_notifications.py -q
```

Expected before PR2: route/auth characterization and read-model snapshots pass; domain metadata and README tests fail until the skeleton exists.

### PR2: Domain Skeleton And Facade Register

- [ ] Create `server/app/domains/account_operations/__init__.py`.
- [ ] Create `server/app/domains/account_operations/README.md`.
- [ ] Document account/group/channel/chain ownership boundaries and explicit exclusions for device task polling and content collection.
- [ ] Keep route behavior in legacy files.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_auth_parity.py server/tests/test_account_operations_domain_boundary.py -q
```

Expected after PR2: auth parity, domain metadata, README, and app import smoke pass.

### PR3: Route Module Compatibility Move

- [ ] Move current `accounts.py` behavior to `accounts_router.py`.
- [ ] Move current `account_groups.py` behavior to `account_groups_router.py`.
- [ ] Move current `channels.py` behavior to `channels_router.py`.
- [ ] Move current `chains.py` behavior to `chains_router.py`.
- [ ] Replace legacy route modules with compatibility aliases that preserve module identity.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_router_facade.py server/tests/test_accounts_api.py server/tests/test_account_groups_api.py server/tests/test_channel_api.py server/tests/test_chains_api.py -q
```

### PR4: Read Models And CRUD Use Cases

- [ ] Move account and account group payload shaping to `read_models.py`.
- [ ] Move account CRUD to `account_use_cases.py`.
- [ ] Move group membership operations to `group_use_cases.py`.
- [ ] Move channel list/detail/item payload shaping and CRUD to `channel_use_cases.py`.
- [ ] Preserve mutation broadcasts through `pair_ws_manager.broadcast_to_admins`: `accounts_changed`, `account_groups_changed`, `channels_changed`, and `new_task_available` where channel mutations currently notify devices/admins.
- [ ] Keep database model ownership unchanged unless a separate ORM graph plan is written.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_read_models.py server/tests/test_account_operations_mutations.py server/tests/test_account_operations_notifications.py server/tests/test_accounts_api.py server/tests/test_account_groups_api.py server/tests/test_channel_api.py server/tests/test_channel_edit_api.py -q
```

### PR5: Chain Orchestration Split

- [ ] Move chain template CRUD to `chain_use_cases.py`.
- [ ] Move chain instance create/list/detail/cancel/retry orchestration to `chain_use_cases.py`.
- [ ] Keep calls into `task_service` or `chain_service` behind adapters.
- [ ] Preserve `chains_changed` broadcasts for chain template and instance mutations.
- [ ] Preserve `pair_ws_manager.send_to_device` behavior for chain cancel/retry paths where current behavior notifies a specific device.
- [ ] Add tests that prove chain behavior does not pull in device polling or content collection logic.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_chain_orchestration.py server/tests/test_account_operations_notifications.py server/tests/test_chains_api.py server/tests/test_chain_service.py server/tests/test_tasks_api.py server/tests/test_task_service.py -q
```

### PR6: Facade Cleanup Gates

- [ ] Inventory imports of `app.routers.accounts`, `app.routers.account_groups`, `app.routers.channels`, and `app.routers.chains`.
- [ ] Move app wiring to domain imports only after compatibility tests prove route parity.
- [ ] Keep legacy router modules until old import path tests are intentionally removed in a cleanup commit.
- [ ] Update README gate status and chain/task ownership notes.

Run:

```powershell
rg -n "app\.routers\.(accounts|account_groups|channels|chains)|from app\.routers import (accounts|account_groups|channels|chains)" server/app server/tests
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_auth_parity.py server/tests/test_account_operations_router_facade.py server/tests/test_account_operations_chain_orchestration.py server/tests/test_account_operations_notifications.py server/tests/test_accounts_api.py server/tests/test_account_groups_api.py server/tests/test_channel_api.py server/tests/test_chains_api.py -q
```

## Boundary And Compatibility Tests

- Route snapshot tests must cover every method/path under `/api/accounts`, `/api/account-groups`, `/api/channels`, and `/api/chains`.
- Auth tests must capture the current split between `verify_admin_token` and role-gated admin creation/mutation routes.
- Read model tests must assert current response keys and ordering for account lists, group members, channel items, chain templates, and chain instances.
- Chain orchestration tests must prove cancel/retry behavior still calls the same underlying services and does not move device task polling into this domain.
- Notification tests must patch/assert `pair_ws_manager.broadcast_to_admins` for `accounts_changed`, `account_groups_changed`, `channels_changed`, `chains_changed`, and `new_task_available`.
- Notification tests must patch/assert `pair_ws_manager.send_to_device` for chain cancel/retry paths where existing behavior targets a device.
- Facade tests must prove each legacy router module is the same module object as its domain router during the alias phase.
- App import smoke must prove `app.main.app` does not register duplicate account, group, channel, or chain routes.
- Existing account, group, channel, chain, and task tests listed in the file map remain compatibility gates for any PR that touches those behaviors.

## Facade Cleanup Gates

- [ ] `server/app/domains/account_operations/README.md` lists every active facade, target module, introduction PR, owner, and exit condition.
- [ ] No cleanup PR may remove legacy account/group/channel/chain router modules while production imports still reference them.
- [ ] `server/app/routers/tasks.py` must not be moved by cleanup unless a separate task-domain or chain-task adapter plan approves it.
- [ ] Realtime cleanup requires `test_account_operations_notifications.py` to prove admin broadcasts and device sends still fire with the current event names.
- [ ] ORM model ownership must not move in this plan unless a separate account operations ORM graph plan exists.
- [ ] Cleanup must not change public route paths, methods, auth dependencies, or response shapes.
- [ ] Final cleanup must include `rg` evidence showing only approved compatibility tests mention legacy router paths.

## Final Verification

Run from the repository root after the final PR in this child plan:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_auth_parity.py server/tests/test_account_operations_domain_boundary.py server/tests/test_account_operations_router_facade.py server/tests/test_account_operations_read_models.py server/tests/test_account_operations_mutations.py server/tests/test_account_operations_chain_orchestration.py server/tests/test_account_operations_notifications.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_accounts_api.py server/tests/test_account_groups_api.py server/tests/test_channel_api.py server/tests/test_channel_edit_api.py server/tests/test_channel_e2e.py server/tests/test_channel_models.py server/tests/test_channel_service.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_chains_api.py server/tests/test_chain_service.py server/tests/test_tasks_api.py server/tests/test_task_service.py -q
rg -n "app\.routers\.(accounts|account_groups|channels|chains)|from app\.routers import (accounts|account_groups|channels|chains)" server/app server/tests
rg -n "accounts_changed|account_groups_changed|channels_changed|chains_changed|new_task_available|pair_ws_manager\.(broadcast_to_admins|send_to_device)" server/app/domains/account_operations server/tests/test_account_operations_notifications.py
```

Expected:

- All new account operations tests pass.
- Existing account, group, channel, chain, and task smoke tests pass.
- Notification tests prove admin broadcasts and device sends still fire with existing event names.
- `rg` output contains only approved compatibility shims or tests until the explicit cleanup PR removes the shims.
- No `ai_video_series`, `device_operations`, or `content_collection` source file is modified unless a PR is explicitly updating documented adapter boundaries.

## GSTACK REVIEW REPORT

Status: PLANNED.
Date: 2026-06-18.
Scope: child implementation plan only; no account operations code is implemented by this document.

| Review | Status | Notes |
|---|---|---|
| CEO Review | INHERITED | Parent plan preserves this domain as a follow-up so account/channel/chain ownership does not get folded into `ai_video_series`. |
| Eng Review | REQUIRED BEFORE CODING | Future implementer should run engineering review after PR1 snapshots clarify account, channel, chain, and task-service dependencies. |
| Design Review | SKIPPED | No UI or product screen changes are planned. |
| DX Review | LIGHTWEIGHT | Plan includes executable PR phases, route surfaces, test files, and cleanup gates. |
| Codex Review | OPTIONAL | Recommended before chain orchestration cleanup because task-service boundaries can be confused with device task polling. |

Decision: proceed only after device and content dependencies are explicit. This plan preserves the approved broad modularization scheme while keeping account operations outside the `ai_video_series` implementation chain.
