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

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Keep `AIModel` persistence and runtime resolution in this domain.
- Keep model consumers, such as Pixelle, image generation, video production, and
  audit, outside this route domain.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
