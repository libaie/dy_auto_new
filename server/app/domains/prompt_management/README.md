# Prompt Management Domain

This domain owns admin prompt template management routes.

## Owned Routes

- `/api/prompt-templates/*`

## Not Owned

- `/api/device/prompt-templates` stays in `device_operations`.

## Current Modules

- `prompt_templates_router.py` owns prompt template AI generation, streaming
  generation, rewrite preview, CRUD, toggle, revision versioning, and realtime
  notification endpoints.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.prompt_templates` | `app.domains.prompt_management.prompt_templates_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Keep prompt service bodies in `app.services.prompt_template_service`.
- Keep device prompt-template polling in `device_operations`.
- Preserve websocket payloads `prompt_templates_updated` and
  `prompt_templates_changed`.
- Preserve logger compatibility for `app.routers.prompt_templates` while tests
  and security checks still patch/capture the legacy path.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports prompt template router from `app.domains.prompt_management`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing prompt rewrite and device prompt template tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.prompt_templates`.
