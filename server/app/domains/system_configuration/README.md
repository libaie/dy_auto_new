# System Configuration Domain

This domain owns admin key-value system configuration routes.

## Owned Routes

- `/api/settings`

## Not Owned

- Health and status routes stay in `system_operations`.
- AI model center routes stay outside this domain.
- Pixelle, Seedance, prompt template, and selector configuration consumers stay
  outside this domain.

## Current Modules

- `settings_router.py` owns settings reads, sensitive-value masking, settings
  updates, and masked secret placeholder preservation.
- `app.db.models.system_configuration` owns the `SystemSetting` ORM class body.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Keep persistence on the existing `system_settings` table.
- Keep request validation on the existing `SettingUpdate` model.
- Keep health/status routes in `system_operations`.
- Preserve route paths, route names, auth dependencies, response shapes,
  sensitive-key masking, masked secret skip behavior, and missing-table fallback
  behavior.
- Do not normalize AI/Pixelle/Seedance configuration consumers in this
  route-boundary migration.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
