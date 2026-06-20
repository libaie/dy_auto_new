# Model Configuration Domain

This domain owns the AI model configuration center routes and default model
seeding helpers.

## Owned Routes

- `/api/ai-models/*`

## Not Owned

- `AIModel` ORM model definition lives in `app.db.models.model_configuration`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Encryption helpers stay in `app.domains.system_configuration.crypto`.
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
- `ai_generator.py` owns `AiGeneratorService`, shared custom and streaming LLM
  calls, sensitive-word retry generation, and the process-wide `ai_generator`
  instance used by app shutdown and domain callers.
- `migration.py` owns legacy Settings, Pixelle, and Seedance configuration
  migration into `AIModel` rows.
- `app.db.models.model_configuration` owns the `AIModel` ORM class body.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.ai_config` | `app.domains.model_configuration.ai_models_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.model_schema` | `app.domains.model_configuration.model_schema` | Keep while legacy tests or callers import schema helpers from `app.services`; remove only after import inventory shows no production legacy imports. |
| `app.services.model_registry` | `app.domains.model_configuration.model_registry` | Remove only after import inventory shows no production legacy imports. |
| `app.services.runtime_model_config` | `app.domains.model_configuration.runtime_model_config` | Keep while dirty or not-yet-moved service modules have approved compatibility imports; remove only after import inventory shows no production legacy imports. |
| `app.services.ai_generator` | `app.domains.model_configuration.ai_generator` | Keep while app startup/shutdown, domain callers, and legacy tests import or monkeypatch the shared generator through `app.services`; remove after import inventory is clean. |
| `app.services.migration` | `app.domains.model_configuration.migration` | Keep while legacy tests or maintenance scripts import migration helpers from `app.services`; remove after import inventory is clean. |
| `app.db_models.AIModel` | `app.db.models.model_configuration.AIModel` | Keep as a compatibility re-export until production imports use the domain model path. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve `DEFAULT_MODELS` and `seed_ai_models` compatibility.
- Preserve monkeypatch compatibility for `app.routers.ai_config.httpx.get`.
- Keep `AIModel` persistence and runtime resolution in this domain.
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
