# Task Operations Domain

This domain will own admin task creation, listing, cancellation, deletion,
batch creation, parameter normalization, and task websocket notifications.

Device polling and device result reporting remain in `device_operations`.
Chain instance orchestration remains in `account_operations`. Content template
and DM sequence business logic remains in `content_collection`.

## PR2 Allowed

- Create `server/app/domains/task_operations/__init__.py`.
- Create this README.
- Expose `DOMAIN_NAME = "task_operations"`.
- Expose `PUBLIC_ROUTE_PREFIX = "/api/tasks"`.
- Document route ownership, neighbor-domain boundaries, notification payloads, facade register, and cleanup gates.

## PR2 Not Allowed

- Do not move route behavior in PR2.
- Do not create `tasks_router.py` in PR2.
- Do not change `/api/tasks/*` paths, methods, auth dependencies, response shapes, task statuses, or websocket payloads.
- Do not move device polling/reporting, chain orchestration, content collection, DM sequence ownership, ORM model ownership, or frontend code.

## PR3 Allowed

- Create `tasks_router.py` from the current `app.routers.tasks` behavior.
- Replace `server/app/routers/tasks.py` with a compatibility facade.
- Keep route paths, methods, auth dependencies, response shapes, and realtime payloads unchanged.

## PR3 Not Allowed

- Do not split helper internals yet.
- Do not change application wiring away from legacy imports yet.
- Do not move device polling/reporting or chain orchestration.

## PR4 Allowed

- Move request schemas to `schemas.py`.
- Move parameter validation and resolution to `param_resolution.py`.
- Move admin task CRUD and batch orchestration to `task_use_cases.py`.
- Move task list/detail payload conventions to `read_models.py`.
- Move websocket helpers to `realtime_events.py`.
- Keep `tasks_router.py` as the FastAPI dependency and HTTP error mapping boundary.

## PR4 Not Allowed

- Do not move device-authenticated polling/reporting routes.
- Do not move account-chain task orchestration.
- Do not move content/DM sequence business ownership.
- Do not change task-service core leasing semantics.

## PR5 Allowed

- Inventory production imports of `app.routers.tasks`.
- Move `server/app/main.py` route wiring to `app.domains.task_operations.tasks_router`.
- Keep `app.routers.tasks` as a compatibility facade for old import paths.

## PR5 Not Allowed

- Do not delete `server/app/routers/tasks.py`.
- Do not remove router facade tests yet.
- Do not change public routes, auth dependencies, response shapes, or websocket payloads.

## Task ORM Boundary Allowed

- Move the `Task` persistence class body to `app.db.models.task_operations`.
- Keep `app.db_models.Task` as a compatibility re-export.
- Update `task_operations` owner-domain code to import `Task` from the domain ORM path.

## Task ORM Boundary Not Allowed

- Do not change task table names, columns, defaults, relationships, or leasing behavior.
- Do not move device polling/reporting, channel execution, chain orchestration, content collection, or DM sequence ownership.

## Ownership Rules

- `app.domains.task_operations` owns the target migration boundary for admin `/api/tasks/*` routes.
- `app.routers.tasks` remains the compatibility import path for `/api/tasks/*` callers outside app wiring.
- `app.domains.task_operations.tasks_router` owns FastAPI route assembly after PR3.
- `app.domains.task_operations.schemas` owns admin task create, batch create, and batch delete request models.
- `app.domains.task_operations.param_resolution` owns admin task parameter validation and resolution helpers.
- `app.domains.task_operations.task_use_cases` owns admin task create, batch create, list, get, cancel, delete, and batch delete orchestration.
- `app.domains.task_operations.realtime_events` owns `new_task_available`, `task_updated`, `tasks_changed`, and direct device `cancel_task` websocket helper calls.
- `app.domains.task_operations.adapters` owns narrow adapter calls into `task_service`, `content_service`, `channel_service`, ORM lookups, and websocket manager APIs.
- `app.domains.task_operations.task_service` owns `TaskService`, task leasing, stale-task recovery, cancellation acknowledgement, and task result persistence.
- `app.db.models.task_operations` owns the `Task` ORM class body; `app.db_models.Task` remains the compatibility import path during migration.
- `app.domains.device_operations.polling` and `app.domains.device_operations.reporting` continue to own device-authenticated task leasing, progress, result, heartbeat, and risk reporting.
- `app.domains.account_operations.chain_use_cases` continues to own chain instance step orchestration.
- `app.domains.content_collection` continues to own content templates and DM sequence business use cases.
- Domain non-router use-case modules must avoid FastAPI imports unless they are route assembly modules.

## Facade Register

| Facade | Target | Introduced | Exit condition |
|---|---|---|---|
| `app.routers.tasks` | `app.domains.task_operations.tasks_router` | Planned PR3 | Route/auth snapshots and existing task API tests pass with the domain router and all callers have an explicit compatibility path. |
| `app.services.task_service` | `app.domains.task_operations.task_service` | 2026-06-20 task service domain migration | Cleanup only after all non-compatibility callers use the domain path and task-service behavior tests pass. |

## Migration Checklist

1. Characterize current route/auth snapshots, response shapes, and realtime events.
2. Add this metadata-only domain skeleton.
3. Move legacy route behavior behind a domain router with a compatibility facade.
4. Split schemas, param resolution, read models, task use cases, realtime events, and adapters into focused modules.
5. Move app route wiring to domain router imports while keeping the legacy facade.
6. Remove compatibility facades only after import inventories and route snapshots prove no behavior drift.

## Test Commands

Run the PR1/PR2 boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_operations_auth_parity.py server/tests/test_task_operations_domain_boundary.py server/tests/test_task_operations_read_models.py server/tests/test_task_operations_notifications.py -q
```

Run the current compatibility checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_tasks_api.py server/tests/test_task_service.py server/tests/test_device_api.py server/tests/test_device_endpoints.py -q
```

## Compatibility Cleanup Gates

Do not remove `app.routers.tasks` until all of these are true:

- `rg "app\.routers\.tasks|from app\.routers import tasks|include_router\(tasks\.router" server/app server/tests` returns only approved compatibility shims, README entries, and cleanup tests.
- `server/tests/test_task_operations_auth_parity.py` passes against the domain router.
- `server/tests/test_task_operations_router_facade.py` proves old and new router import paths expose the same route objects during the alias phase.
- `server/tests/test_task_operations_notifications.py` proves task websocket payloads still reach admins and devices.
- `server/tests/test_device_operations_polling_reporting.py` proves device polling/reporting ownership remains outside this domain.
- `server/tests/test_account_operations_chain_orchestration.py` proves chain orchestration ownership remains outside this domain.
- `app.main` imports the task router from `app.domains.task_operations`.

Do not move device polling/reporting, chain orchestration, content collection, DM sequence ownership, or additional persistence class bodies until separate plans approve those boundaries.
