# Domain Service Import Inventory Design

Date: 2026-06-20

## Goal

Prevent new business-domain code from silently depending on the legacy
`app.services` layer while the remaining large service migrations are still in
progress.

## Current Context

Many small helpers have already moved into `server/app/domains/*`, but several
large services such as `ai_generator`, `image_creation_service`,
`production_queue_service`, `agency_orchestrator`, and video production
orchestrators still have active WIP in `server/app/services`. Moving them now
would mix unrelated work into this refactor.

## Design

Add a single architecture inventory test:

- scan every Python file under `server/app/domains`;
- collect `from app.services...` and `import app.services...` imports with
  Python `ast`;
- compare the result to an explicit temporary allowlist.

The allowlist is not approval for permanent coupling. It is the current
migration inventory. Each future service migration should remove entries from
the allowlist when the corresponding domain code imports a domain module
directly.

## Non-Goals

- Do not migrate the remaining dirty large services in this slice.
- Do not change runtime behavior.
- Do not touch existing WIP test files.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py -q
```

Expected: the test passes only when the current `app.services` import inventory
matches the explicit allowlist.
