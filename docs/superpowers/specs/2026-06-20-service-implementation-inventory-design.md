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
- separately inventories files that import `app.domains` but still define
  top-level classes or functions;
- compares all remaining implementation file names against an explicit
  temporary allowlist.
- requires every temporary allowlist entry to name its intended target domain.
- verifies that every target value matches an existing directory under
  `server/app/domains`.

The allowlists record the current migration debt. Each future service migration
should remove the migrated file name from the matching allowlist when the
legacy service becomes a thin facade with no top-level implementation. The
mixed-facade allowlist prevents a large service from looking fully migrated
just because it already imports a domain module. The target-domain map keeps
the plain implementation debt actionable instead of leaving a flat list with no
migration destination. `ai_generator.py` is mapped to `model_configuration` for
now because it owns model/provider API invocation plumbing; a later slice can
split it further if a dedicated generation domain is introduced.

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
the explicit allowlist, mixed facade files match their allowlist, every
allowlisted implementation file has a target domain, and each target domain
exists.
