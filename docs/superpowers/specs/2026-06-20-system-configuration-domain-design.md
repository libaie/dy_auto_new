# System Configuration Domain Design

Date: 2026-06-20

## Goal

Move admin system-settings route ownership out of the flat `app.routers`
folder and into `app.domains.system_configuration` without changing public API
behavior.

This domain owns the admin-facing key-value configuration API for reading
settings, masking sensitive values, and updating settings while preserving
masked secret placeholders.

## Scope

The new domain owns:

- `GET /api/settings`;
- `PUT /api/settings`;
- route-local sensitive-key masking constants;
- route assembly and auth dependencies for those endpoints.

The migration keeps `app.routers.settings` as a compatibility facade.

## Non-Goals

- Do not move `SystemSetting` ORM model definitions.
- Do not move `SettingUpdate` request model definitions.
- Do not move AI model center, Pixelle, Seedance, prompt template, or selector
  configuration consumers.
- Do not change sensitive-key masking, masked secret skip behavior, route paths,
  route names, auth dependencies, response shapes, or fallback behavior when
  the `system_settings` table is missing.
- Do not merge this into `system_operations`; health/status routes stay separate
  from configuration management.

## Target Structure

```text
server/app/domains/system_configuration/
  __init__.py
  README.md
  settings_router.py
```

This is a route-boundary migration. Later work can split configuration
use-cases or normalize legacy configuration consumers after the domain import
boundary is stable.

## Compatibility Strategy

Legacy imports stay valid through a module alias:

```python
from app.domains.system_configuration import settings_router as _settings_router
sys.modules[__name__] = _settings_router
globals().update(_settings_router.__dict__)
```

This keeps old imports of `app.routers.settings` resolving to the same module
object as `app.domains.system_configuration.settings_router` during the
compatibility phase.

## Tests

The migration adds:

- route/auth snapshot tests for `/api/settings`;
- boundary tests for metadata, README, facade thickness, route registration,
  main wiring, and separation from `system_operations`;
- facade identity tests proving old and new imports resolve to the same module
  object while compatibility is active.

Existing settings endpoint tests continue to cover masking, masked-value skip,
new-value updates, key creation, and empty settings responses.
