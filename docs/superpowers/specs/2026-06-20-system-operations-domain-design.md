# System Operations Domain Design

Date: 2026-06-20

## Goal

Move system operational health route ownership out of the flat `app.routers`
folder and into `app.domains.system_operations` without changing public API
behavior.

This domain owns server readiness/health checks for migration state, paid
provider capability, worker runtime configuration, and real-provider scene
readiness.

## Scope

The new domain owns:

- `/api/system/*` route assembly;
- `/api/system/health` response construction;
- route-local helpers for migration schema checks, provider capability
  summarization, worker runtime checks, and scene readiness checks.

The migration keeps `app.routers.system_health` as a compatibility facade because
existing tests monkeypatch helper functions through that import path.

## Non-Goals

- Do not move the Root `/health` endpoint from `app.main`.
- Do not move provider capability services, provider stage executors, ORM models,
  or migration logic in this slice.
- Do not change health response shape, HTTP status behavior, auth dependencies,
  or helper function names.
- Do not move admin dashboards, stats, or selector management into this domain.

## Target Structure

```text
server/app/domains/system_operations/
  __init__.py
  README.md
  system_health_router.py
```

This is a route-boundary migration. Later work can split health read models or
provider readiness checks once the domain import boundary is stable.

## Compatibility Strategy

Legacy imports remain valid through a module alias:

```python
from app.domains.system_operations import system_health_router as _system_health_router
sys.modules[__name__] = _system_health_router
globals().update(_system_health_router.__dict__)
```

This keeps monkeypatches against `app.routers.system_health._migration_health`,
`_provider_capability_health`, and `_capability_for_model` working during the
migration.

## Tests

The migration adds:

- route/auth snapshot tests for `/api/system/*`;
- boundary tests for metadata, README, facade thickness, and route registration;
- facade identity tests proving old and new imports resolve to the same module
  object while compatibility is active.
