# Account Operations Domain

This domain will own account CRUD, account groups and membership, channels,
channel items, chain templates, and chain instance orchestration metadata.

Device task polling remains in `device_operations`. Content collection and DM
business use cases remain in `content_collection`.

## Ownership Rules

- `app.domains.account_operations` owns the target migration boundary for `/api/accounts/*`, `/api/account-groups/*`, `/api/channels/*`, and `/api/chains/*`.
- `app.domains.account_operations.read_models` owns account, group, member, channel, channel item, chain template, chain instance, and chain task payload shaping.
- `app.domains.account_operations.account_use_cases` owns account CRUD and account status behavior.
- `app.domains.account_operations.group_use_cases` owns account group CRUD and membership add/remove behavior.
- `app.domains.account_operations.channel_use_cases` owns channel CRUD, channel item mutation, batch item edits, and channel status transitions.
- `app.domains.account_operations.channel_service` owns `ChannelService` channel creation, item claim/recovery, quota/risk-control handling, and channel stats.
- `app.domains.account_operations.chain_use_cases` owns chain template CRUD and chain instance create/list/detail/cancel/retry orchestration.
- `app.domains.account_operations.chain_service` owns `ChainService` chain instance orchestration, step task creation, and chain advancement.
- `app.domains.account_operations.realtime_events` owns `accounts_changed`, `account_groups_changed`, `channels_changed`, `chains_changed`, and `new_task_available` websocket helper calls.
- `app.domains.account_operations.adapters` owns narrow adapter calls into current ORM sessions, `channel_service`, `chain_service`, and `task_service`.
- `app.db.models.account_operations` owns the `Account`, `AccountGroup`,
  `AccountGroupMember`, `ChainTemplate`, `ChainInstance`, `Channel`, and
  `ChannelItem` ORM class bodies.
- Task polling and task route ownership remain outside this domain unless a separate task-domain or chain-task adapter plan approves that boundary.
- Domain non-router use-case modules must avoid FastAPI imports unless they are route assembly modules.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Test Commands

Run the PR1/PR2 boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_auth_parity.py server/tests/test_account_operations_domain_boundary.py server/tests/test_account_operations_read_models.py server/tests/test_account_operations_notifications.py -q
```


```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_accounts_api.py server/tests/test_account_groups_api.py server/tests/test_channel_api.py server/tests/test_channel_edit_api.py server/tests/test_channel_e2e.py server/tests/test_channel_models.py server/tests/test_channel_service.py server/tests/test_chains_api.py server/tests/test_chain_service.py server/tests/test_tasks_api.py server/tests/test_task_service.py -q
```

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
