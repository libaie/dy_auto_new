# Task Operations Domain

This domain will own admin task creation, listing, cancellation, deletion,
batch creation, parameter normalization, and task websocket notifications.

Device polling and device result reporting remain in `device_operations`.
Chain instance orchestration remains in `account_operations`. Content template
and DM sequence business logic remains in `content_collection`.

## Ownership Rules

- `app.domains.task_operations` owns the target migration boundary for admin `/api/tasks/*` routes.
- `app.domains.task_operations.tasks_router` owns FastAPI route assembly after PR3.
- `app.domains.task_operations.schemas` owns admin task create, batch create, and batch delete request models.
- `app.domains.task_operations.param_resolution` owns admin task parameter validation and resolution helpers.
- `app.domains.task_operations.task_use_cases` owns admin task create, batch create, list, get, cancel, delete, and batch delete orchestration.
- `app.domains.task_operations.realtime_events` owns `new_task_available`, `task_updated`, `tasks_changed`, and direct device `cancel_task` websocket helper calls.
- `app.domains.task_operations.adapters` owns narrow adapter calls into `task_service`, `content_service`, `channel_service`, ORM lookups, and websocket manager APIs.
- `app.domains.task_operations.task_service` owns `TaskService`, task leasing, stale-task recovery, cancellation acknowledgement, and task result persistence.
- `app.domains.device_operations.polling` and `app.domains.device_operations.reporting` continue to own device-authenticated task leasing, progress, result, heartbeat, and risk reporting.
- `app.domains.account_operations.chain_use_cases` continues to own chain instance step orchestration.
- `app.domains.content_collection` continues to own content templates and DM sequence business use cases.
- Domain non-router use-case modules must avoid FastAPI imports unless they are route assembly modules.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Test Commands

Run the PR1/PR2 boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_auth_parity.py server/tests/test_task_operations_domain_boundary.py server/tests/test_task_operations_read_models.py server/tests/test_task_operations_notifications.py -q
```


```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_tasks_api.py server/tests/test_task_service.py server/tests/test_device_api.py server/tests/test_device_endpoints.py -q
```

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
