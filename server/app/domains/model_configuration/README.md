# Model Configuration Domain

This domain owns the AI model configuration center routes and default model
seeding helpers.

## Owned Routes

- `/api/ai-models/*`

## Not Owned

- `AIModel` ORM model definitions stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Encryption helpers stay in `app.services.crypto`.
- raw schema data stays in `app.data.model_schema_data`.
- Pixelle, Seedance, and audit execution routes stay in their own domains or
  routers.

## Current Modules

- `ai_models_router.py` owns `ModelCreate`, `ModelUpdate`, `DEFAULT_MODELS`,
  `seed_ai_models`, model CRUD endpoints, the model schema endpoint, connection
  test helpers, blank-secret preservation, and SSRF protection.
- `model_schema.py` owns `get_schema_payload`, `get_provider_preset`, scene
  lookups, and provider lists; raw schema data stays in
  `app.data.model_schema_data`.
- `model_registry.py` owns `ModelResolutionError`, `get_model_for_scene`,
  scene-based AIModel selection, decrypted runtime credentials, and repair
  messages.
- `runtime_model_config.py` owns `RuntimeModelConfigError`,
  `resolve_runtime_model_config`, `resolve_image_model_for_capability`,
  `_model_supports_capability`, and `redact_runtime_model_config`.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.ai_config` | `app.domains.model_configuration.ai_models_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.model_schema` | `app.domains.model_configuration.model_schema` | Keep while legacy tests or callers import schema helpers from `app.services`; remove only after import inventory shows no production legacy imports. |
| `app.services.model_registry` | `app.domains.model_configuration.model_registry` | Keep while `video_production_service` has an approved video production compatibility import; remove only after import inventory shows no production legacy imports. |
| `app.services.runtime_model_config` | `app.domains.model_configuration.runtime_model_config` | Keep while dirty or not-yet-moved service modules have approved compatibility imports; remove only after import inventory shows no production legacy imports. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve `DEFAULT_MODELS` and `seed_ai_models` compatibility.
- Preserve monkeypatch compatibility for `app.routers.ai_config.httpx.get`.
- Keep `AIModel` persistence and runtime resolution in shared layers.
- Keep model consumers, such as Pixelle, image generation, video production, and
  audit, outside this route domain.
- Keep compatibility for `app.services.runtime_model_config` until all service
  modules have moved to domain imports or documented approved compatibility
  imports.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `ai_models_router` and `seed_ai_models` from
  `app.domains.model_configuration`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing model center tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.ai_config`.

Do not remove the legacy runtime model config facade until all of these are true:

- `rg "app\.services\.runtime_model_config" server/app server/tests` returns
  only compatibility tests, migration docs, or service modules whose domains
  have not moved yet.
- Direct domain runtime config coverage proves `resolve_runtime_model_config`,
  `resolve_image_model_for_capability`, scene/capability support checks, and
  `redact_runtime_model_config` behavior.
- Domain-owned production modules import
  `app.domains.model_configuration.runtime_model_config` directly.
