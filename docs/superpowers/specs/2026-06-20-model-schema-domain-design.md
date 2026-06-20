# Model Schema Domain Design

Date: 2026-06-20

## Goal

Move AI model schema helper ownership from `app.services.model_schema` into
`app.domains.model_configuration.model_schema` without changing
`/api/ai-models/schema`, provider preset fallback behavior, or legacy imports.

## Approved Approach

Move the current helper implementation to
`server/app/domains/model_configuration/model_schema.py`.

Keep `app.services.model_schema` as a `sys.modules` compatibility facade.
Update `model_configuration.ai_models_router` to import the domain helper
directly. Keep `app.data.model_schema_data` in place for this slice.

## Boundaries

- Preserve `get_scene_by_key`, `get_providers_for_scene`,
  `get_provider_preset`, and `get_schema_payload`.
- Preserve legacy imports such as
  `from app.services.model_schema import get_provider_preset`.
- Preserve `app.data.model_schema_data` as the raw schema data owner.
- Do not change model CRUD, seed defaults, encryption, runtime resolution, API
  paths, auth dependencies, or response shapes.

## Verification

- Add a boundary test proving spec/plan coverage, domain file existence,
  facade thinness, module identity, parent package import identity, router
  direct domain import, README ownership, and fallback behavior.
- Run the model schema endpoint tests after migration.
