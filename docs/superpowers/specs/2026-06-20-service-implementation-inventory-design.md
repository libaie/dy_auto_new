# Service Implementation Inventory Design

Date: 2026-06-20

## Goal

Prevent new business implementation files from being added to
`server/app/services` while server business logic is being moved into
`server/app/domains`.

## Current Context

Most small legacy service files are now compatibility facades that import their
implementation from `app.domains.*`. A smaller set of large service files still
contains implementation code, and many of those files currently have unrelated
WIP in the worktree. Moving them in this slice would mix concerns.

## Design

Add one inventory test that:

- scans direct Python files under `server/app/services`;
- ignores `__init__.py`;
- treats a file containing `from app.domains` as a facade;
- compares all remaining implementation file names against an explicit
  temporary allowlist.

The allowlist records the current migration debt. Each future service migration
should remove the migrated file name from this allowlist when the legacy service
becomes a facade.

## Non-Goals

- Do not migrate the remaining large services in this slice.
- Do not change runtime behavior.
- Do not touch existing dirty service files.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: the test passes only when the set of non-facade service files matches
the explicit allowlist.
