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

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.settings` | `app.domains.system_configuration.settings_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.crypto` | `app.domains.system_configuration.crypto` | Sensitive-setting crypto compatibility; remove after production callers use the domain path. |

## Boundaries

- Keep persistence on the existing `SystemSetting` ORM model.
- Keep request validation on the existing `SettingUpdate` model.
- Keep health/status routes in `system_operations`.
- Preserve route paths, route names, auth dependencies, response shapes,
  sensitive-key masking, masked secret skip behavior, and missing-table fallback
  behavior.
- Do not normalize AI/Pixelle/Seedance configuration consumers in this
  route-boundary migration.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports the settings router from
  `app.domains.system_configuration`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing settings endpoint tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.settings`.
