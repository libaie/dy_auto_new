# Task Service Domain Design

## Goal

Move the DB-backed task scheduling service implementation into the
`task_operations` domain while keeping the legacy `app.services.task_service`
import path working.

## Current Problem

`server/app/services/task_service.py` owns task creation, leasing, stale-task
recovery, cancellation acknowledgement, and result reporting. Several domain
modules import that service through `app.services.task_service`, which keeps a
core task workflow outside the business domain tree and weakens the modular
boundary.

## Options

1. Move the full implementation into
   `app.domains.task_operations.task_service` and leave a thin compatibility
   facade at `app.services.task_service`.
2. Keep the implementation in `app.services.task_service` and only update
   import comments and README ownership.
3. Split `TaskService` into smaller files during the move.

## Decision

Use option 1. It changes ownership without changing behavior. Option 2 does not
improve the real dependency boundary. Option 3 is too large for this slice
because task leasing semantics are sensitive and should be split under separate
tests later.

## Scope

In scope:

- Create `server/app/domains/task_operations/task_service.py` as the canonical
  implementation module.
- Replace `server/app/services/task_service.py` with a compatibility facade
  that aliases the domain module.
- Update domain-owned imports to use
  `app.domains.task_operations.task_service`.
- Update the task-operations README facade register.
- Add tests proving the canonical module, facade identity, and domain import
  boundary.

Out of scope:

- No changes to task routes, public API shapes, task statuses, websocket
  payloads, retry counts, stale recovery rules, or lease validation.
- No cleanup of legacy imports in tests or non-domain compatibility callers.
- No split of `TaskService` methods into smaller services.

## Components

- `app.domains.task_operations.task_service`: canonical implementation and
  owner of `TaskService`, `task_service`, `_db_task_to_pydantic`, and
  `MAX_RETRIES`.
- `app.services.task_service`: legacy facade that resolves to the domain module.
- `app.domains.task_operations.adapters`: imports the canonical task service
  alongside other domain-owned adapters.
- `app.domains.device_operations.polling`,
  `app.domains.device_operations.reporting`, and
  `app.domains.device_operations.status_lifecycle`: device workflows that call
  the canonical task service directly.
- `app.domains.account_operations.channel_service`: channel claiming helper that
  converts DB tasks through the canonical task conversion helper.

## Data Flow

Task data flow is unchanged. Existing call sites still call the same
`TaskService` methods and receive the same Pydantic task models. The only
change is import resolution: new domain callers use the canonical domain path,
while old callers may keep importing the legacy path during the compatibility
phase.

## Testing

Add a domain boundary test that fails before the move and passes after:

- The spec and plan mention both the canonical and legacy import paths.
- The domain module contains `TaskService`, `task_service`,
  `_db_task_to_pydantic`, and `MAX_RETRIES`.
- The legacy file is a thin facade and no longer contains the implementation.
- Importing `app.services.task_service` returns the same module object as
  `app.domains.task_operations.task_service`.
- Domain modules no longer import `app.services.task_service`.
- The task-operations README registers the new facade.

Run the new boundary test and the existing task service test after migration.

## Risks

The main risk is breaking imports that expect the legacy module identity. The
facade uses the same `sys.modules` alias pattern already used by router and
service facades in this project, so legacy callers continue to work while the
canonical owner moves.
